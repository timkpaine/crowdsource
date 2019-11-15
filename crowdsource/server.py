import sys
import os.path
import logging
import tornado.ioloop
import tornado.web
# from datetime import datetime
from perspective import Table, PerspectiveManager, PerspectiveTornadoHandler
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from traitlets.config.application import Application
from traitlets import Int, Unicode, List, Bool
from .handlers import HTMLOpenHandler, \
    LoginHandler, \
    LogoutHandler, \
    RegisterHandler, \
    AdminHandler, \
    APIKeyHandler, \
    CompetitionHandler, \
    SubmissionHandler, \
    LeaderboardHandler
from .persistence.models import Base, Client, Competition, Submission


class Crowdsource(Application):
    name = 'crowdsource'
    description = 'crowdsource'
    port = Int(default_value=8080, help="Port to run on").tag(config=True)
    basepath = Unicode(default_value='/', help="Base URL (for reverse proxies)").tag(config=True)
    apipath = Unicode(default_value='/api/v1/', help="API base URL (for reverse proxies)").tag(config=True)
    wspath = Unicode(default_value='ws:0.0.0.0:{}/', help="websocket url").tag(config=True)

    sql_url = Unicode(default_value='sqlite:///crowdsource.db', help="SQL Alchemy url").tag(config=True)

    proxies = List(default_value=[])
    handlers = List(default_value=[])
    debug = Bool(default_value=True).tag(config=True)
    cookie_secret = Unicode(default_value="61oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=")
    sql = Bool(default_value=True).tag(config=True)

    aliases = {
        'port': 'Crowdsource.port',
        'basepath': 'Crowdsource.basepath',
        'wspath': 'Crowdsource.wspath',
        'debug': 'Crowdsource.debug',
    }

    flags = {
        "debug": ({"Crowdsource": {
            "debug": True
        }}, "run in debug mode")
    }

    def start(self):
        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        # Port
        self.port = int(os.environ.get('PORT', self.port))

        # Set websocket path
        self.wspath = self.wspath.format(self.port)

        self._stash = []
        engine = create_engine(self.sql_url, echo=False)
        Base.metadata.create_all(engine)

        # fetch clients
        self.sessionmaker = sessionmaker(bind=engine)
        session = self.sessionmaker()
        clients = session.query(Client).all()

        self._clients = {c.client_id: c for c in clients}

        # Perspective managers
        self._manager = PerspectiveManager()
        self._admin_manager = PerspectiveManager()

        # Public perspective tables
        self._competitions = Table(list(c.to_dict() for c in session.query(Competition).all()))
        self._leaderboards = Table(list(s.to_dict() for s in session.query(Submission).all()))
        # self._leaderboards = Table(list(s.to_dict() for s in session.query(Submission).all() if datetime.now() > s.competition.expiration))

        self._manager.host_table("competitions", self._competitions)
        self._manager.host_table("leaderboards", self._leaderboards)

        # Private perspective tables
        self._all_clients = Table(list(s.to_dict() for s in session.query(Client).all()))
        self._all_competitions = Table(list(c.to_dict() for c in session.query(Competition).all()))
        self._all_submissions = Table(list(s.to_dict() for s in session.query(Submission).all()))

        self._admin_manager.host_table("clients", self._all_clients)
        self._admin_manager.host_table("competitions", self._all_competitions)
        self._admin_manager.host_table("submissions", self._all_submissions)

        # TODO to remove
        self._submissions = Table({"a": int})  # TODO remove

        # for offline storage
        self._stash = []

        root = os.path.join(os.path.dirname(__file__), 'assets')
        static = os.path.join(root, 'static')

        context = {'sessionmaker': self.sessionmaker,
                   'clients': self._clients,
                   'all_clients': self._all_clients,
                   'competitions': self._competitions,
                   'all_competitions': self._all_competitions,
                   'submissions': self._submissions,
                   'all_submissions': self._all_submissions,
                   'leaderboards': self._leaderboards,
                   'stash': self._stash,
                   'basepath': self.basepath,
                   'wspath': self.wspath,
                   'proxies': 'test'}

        default_handlers = [
            (r"/", HTMLOpenHandler, {'template': 'index.html', 'context': context}),
            (r"/index.html", HTMLOpenHandler, {'template': 'index.html', 'context': context, 'template_kwargs': {}}),
            (r"/home", HTMLOpenHandler, {'template': 'home.html', 'context': context}),
        ]

        default_handlers.extend([
            (r"/api/v1/login", LoginHandler, context),
            (r"/api/v1/logout", LogoutHandler, context),
            (r"/api/v1/register", RegisterHandler, context),
            (r"/api/v1/admin", AdminHandler, context),
            (r"/api/v1/apikeys", APIKeyHandler, context),
            (r"/api/v1/competition", CompetitionHandler, context),
            (r"/api/v1/wscompetition", PerspectiveTornadoHandler, {"manager": self._manager, "check_origin": True}),
            (r"/api/v1/submission", SubmissionHandler, context),
            (r"/api/v1/leaderboard", LeaderboardHandler, context),
            (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": static}),
            (r"/(.*)", HTMLOpenHandler, {'template': '404.html', 'context': context})
        ])

        for handler in self.handlers:
            for i, default in enumerate(default_handlers):
                if default[0] == handler[0]:
                    # override default handler
                    d = default[2]
                    d.update(handler[2])
                    default_handlers[i] = (handler[0], handler[1], d)

        settings = {
            "cookie_secret": self.cookie_secret,
            "login_url": self.basepath + "login",
            "debug": self.debug,
            "template_path": os.path.join(root, 'templates'),
        }

        application = tornado.web.Application(default_handlers, **settings)

        logging.critical('LISTENING: %d', self.port)
        application.listen(self.port)
        tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    Crowdsource.launch_instance(sys.argv)
