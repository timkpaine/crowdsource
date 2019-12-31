import logging
import six
import tornado.gen
import tornado.web
import ujson
from datetime import datetime
from tornado.concurrent import run_on_executor
from .base import AuthenticatedHandler
from .validate import validate_submission_get, validate_submission_post
from ..persistence.models import Submission, Competition
from ..types.submission import SubmissionSpec
from ..types.utils import fetchDataset, checkAnswer
from ..enums import CompetitionType


class SubmissionHandler(AuthenticatedHandler):
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self):
        yield self._get()

    @run_on_executor
    def _get(self):
        '''Get the current list of competition ids'''
        data = self._validate(validate_submission_get)

        res = []
        with self.session() as session:
            # first, grade any pending submissions that are now available
            self.score_laters(session)
            submissions = session.query(Submission).all()

            for c in submissions:
                submission_id = data.get('submission_id', ())
                cpid = data.get('competition_id', ())
                clid = data.get('user_id', ())
                user_username = data.get('user_username', ())
                t = data.get('type', '')

                if submission_id and c.submission_id not in submission_id:
                    continue
                if cpid and c.competition_id not in cpid:
                    continue
                if clid and c.user_id not in clid:
                    continue
                if t and CompetitionType(t) != c.competition.spec.type:
                    continue
                if user_username and c.user.username != user_username:
                    continue

                # only allow if im the submitter or the competition owner
                if (int(self.current_user) != c.user_id) and (int(self.current_user) != c.competition.user_id):
                    continue

                # check if expired and turn off if necessary
                if datetime.now() > c.competition.expiration:
                    c.competition.active = False

                d = c.to_dict(private=True)

                d['score'] = round(d['score'], 2)
                res.append(d)

        self.write(ujson.dumps(res))

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def post(self):
        '''Register a competition. Competition will be assigned a session id'''
        yield self._post()

    @run_on_executor
    def _post(self):
        data = self._validate(validate_submission_post)

        submission = data['submission']
        user_id = int(self.current_user)
        competition_id = data['competition_id']

        with self.session() as session:
            competition = session.query(Competition).filter_by(competition_id=int(competition_id)).first()
            if not competition:
                self._set_400("Competition not registered")
                return

            if datetime.now() > competition.expiration:
                competition.active = False
                self.write('{}')
                return

            try:
                spec = SubmissionSpec.from_dict(submission)
                submission = Submission.from_spec(user_id=user_id,
                                                  competition_id=competition_id,
                                                  competition=competition,
                                                  spec=spec)
            except (KeyError, ValueError, AttributeError):
                self._set_400("Submission malformed")

            # persist
            session.commit()
            session.refresh(submission)

            if not submission.submission_id:
                self._set_400("Submission malformed")

            # put in perspective
            self._submissions.update([submission.to_dict()])

            submission_id = submission.submission_id

            # calculate result if immediate
            if competition.answer_delay <= 0:
                score = self.score(submission, session)
            else:
                self.score_later(submission)
                score = {'submission_id': submission_id}

            self._writeout(ujson.dumps(score), 'Registering submission %s from %s', submission_id, submission.user_id)

    def score(self, submission, session):
        logging.info("SCORING %s FOR %s", str(submission.submission_id), submission.competition_id)
        score = checkAnswer(submission)
        submission.score = score
        session.commit()

        # put in perspective
        d = submission.to_dict()
        self._all_submissions.update([d])
        self._leaderboards.update([d])

        return d

    def score_later(self, submission):
        logging.info("Stashing submission %s for competition %s to score later", submission.submission_id, submission.competition_id)
        self._to_score_later.append(submission)

    def score_laters(self, session):
        to_score_now = [s for s in self._to_score_later if datetime.now() > s.competition.expiration]
        logging.info('Scoring %s submissions now', len(to_score_now))

        ret = []

        for s in to_score_now:
            competition = s.competition
            df = fetchDataset(competition)

            # FIXME
            if isinstance(competition.targets, dict):
                df = df[df[competition.dataset_key].isin(list(set(competition.current_state[competition.dataset_key].values)))][competition.current_state.columns]
            elif isinstance(competition.targets, list):
                df = df[competition.spec.targets][competition.current_state.columns]
            elif isinstance(competition.targets, six.string_types):
                df = df[[competition.spec.targets]][competition.current_state.columns]

            cur = len(competition.current_state.index)
            if len(df.index) > cur:
                competition.answer = df[df.index == df.index[-1]]
                ret.append(self.score(s, session))
                self._to_score_later.remove(s)

            else:
                logging.info('SKIPPING %d', s.id)

        logging.info('%s left to score', len(self._to_score_later))
        return ret
