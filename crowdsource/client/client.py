import os
import pandas as pd
import threading
import time
import ujson
from tornado_sqlalchemy_login.utils import safe_get, safe_post_cookies, construct_path
from traitlets import HasTraits
from .samples_mixin import SamplesMixin
from ..types.competition import CompetitionSpec
from ..types.submission import SubmissionSpec
from ..enums import DatasetFormat
from ..exceptions import MalformedCompetitionSpec


class Thread(threading.Thread):
    def __init__(self, target, competitionSpec, **kwargs):
        threading.Thread.__init__(self)
        self._mytarget = target
        self._kwargs = kwargs
        self._comp = competitionSpec

    def run(self):
        self._return = self._mytarget(self._comp, **self._kwargs)

    def join(self, timeout=.1):
        threading.Thread.join(self, timeout)

        if threading.Thread.isAlive(self):
            return None

        if not hasattr(self, '_return'):
            return None

        return self._return


class Client(SamplesMixin, HasTraits):
    def __init__(self, serverHost, key=None, secret=None, cookies=None, proxies=None):
        '''Constructor for client object

        Client is the primary API interface for
        communicating with the server

        Arguments:
            serverhost {str} -- IP/port of the competition server
            key {str} -- participant api key - key
            secret {str} -- participant api key - secret
        '''
        self._host = serverHost

        self._key = key or os.environ["CROWDSOURCE_KEY"]
        self._secret = secret or os.environ["CROWDSOURCE_SECRET"]
        self._cookies = cookies if cookies else None
        self._proxies = proxies if proxies else None
        self._am_registered = False

        self.register()

        self._callbacks = {}  # Callbacks by type
        self._competitions = {}  # Competitions I am competing in
        self._running = None  # Running competition thread

        self._my_competitions = []  # Competitions I am hosting

    def register(self):
        '''Register client with the competitions host'''
        if not self._am_registered:
            resp, cookies = safe_post_cookies(construct_path(self._host, 'api/v1/login'), data={"key": self._key, "secret": self._secret}, cookies=self._cookies, proxies=self._proxies)
        self._cookies = cookies

    def start_competition(self, competition):
        '''Host a competition

        Arguments:
            competition {CompetitionStruct} -- A competition struct
        '''
        if not isinstance(competition, CompetitionSpec):
            raise MalformedCompetitionSpec()

        self.register()
        resp, _ = safe_post_cookies(construct_path(self._host, 'api/v1/competition'),
                                    data=ujson.dumps({'spec': competition.to_dict()}), cookies=self._cookies, proxies=self._proxies)
        self._my_competitions.append(resp)

    def compete(self, competitionType, callback, **callbackArgs):
        '''Ping server for competition_id, on update call callback'''
        if not self._competitions.get(competitionType):
            self._competitions[competitionType] = []

        self._callbacks[competitionType] = self._callbacks[competitionType] + [callback] \
            if self._callbacks.get(competitionType) \
            else [callback]

        def ping_and_run():
            while(True):
                threads = {}
                competitions = self.competitions()
                for comp in competitions:
                    competition_id = comp['competition_id']
                    c = comp['spec']

                    for callback in self._callbacks.get(c.type.value, []):
                        if (competition_id, callback) not in self._competitions[competitionType]:

                            # New competition or callback, run
                            t = Thread(target=callback, competitionSpec=c, **callbackArgs)

                            # start thread
                            t.start()
                            threads[t] = (competition_id, callback)

                            self._competitions[competitionType].append((competition_id, callback))

                remove = []
                for t in threads:
                    # attempt to join
                    ret = t.join(1)
                    if not t.isAlive():

                        # pop from thread list
                        competition_id, _ = threads[t]
                        if ret is None or ret.empty:
                            pass
                        else:
                            self.submit(competition_id, ret)
                            remove.append(t)

                for t in remove:
                    threads.pop(t)

                # ping every second
                time.sleep(2)

        if not self._running:
            t = threading.Thread(target=ping_and_run)
            t.start()
            self._running = True

    def leaderboards(self, submissionId=None, clientId=None, competitionId=None, type=None):
        '''Query Crowdsource server for leaderboard info
        Keyword Arguments:
          submissionId {[int/str]} -- list of submission ids to filter on
          clientId {[int/str]} -- list of client ids to filter on
          competitionId {[int/str]} -- list of competition ids to filter on
          type {[int/str]} -- list of competition types to filter on

        Returns:
          list of submissions satisfying the above filtering
        '''
        self.register()

        send = {}
        if submissionId:
            send['submission_id'] = submissionId
        if clientId:
            send['client_id'] = clientId
        if competitionId:
            send['competition_id'] = competitionId
        if type:
            send['type'] = type
        ret = safe_get(construct_path(self._host, 'api/v1/submission'), data=ujson.dumps(send), cookies=self._cookies, proxies=self._proxies)
        return ret  # TODO parse into the correct type

    def competitions(self, clientId=None, competitionId=None, type=None):
        '''Query Crowdsource server for competition info
        Keyword Arguments:
          clientId {[int/str]} -- list of client ids to filter on
          competitionId {[int/str]} -- list of competition ids to filter on
          type {[int/str]} -- list of competition types to filter on

        Returns:
          list of competitions satisfying the above filtering
        '''
        self.register()

        send = {}
        if competitionId:
            send['competition_id'] = competitionId
        if clientId:
            send['client_id'] = clientId
        if type:
            send['type'] = type

        ret = safe_get(construct_path(self._host, 'api/v1/competition'), data=ujson.dumps(send), cookies=self._cookies, proxies=self._proxies)

        ret = [{'competition_id': x['competition_id'], 'spec': CompetitionSpec.from_dict(x)} for x in ret]
        return ret

    def submit(self, competitionId, submission, submission_format=DatasetFormat.JSON):
        '''Submit answers to a competition'''
        self.register()
        if isinstance(submission, pd.DataFrame):
            submission = submission.to_json()
            submission_format = DatasetFormat.JSON
        if not isinstance(submission, SubmissionSpec):
            submission = SubmissionSpec(competitionId, submission, submission_format)
        resp, _ = safe_post_cookies(construct_path(self._host, 'api/v1/submission'),
                                    data=ujson.dumps({'competition_id': competitionId, 'submission': submission.to_dict()}),
                                    cookies=self._cookies,
                                    proxies=self._proxies)
        return resp

    def users(self):
        '''Return a list of active user ids'''
        self.register()
        return safe_get(construct_path(self._host, 'api/v1/register'), cookies=self._cookies, proxies=self._proxies)
