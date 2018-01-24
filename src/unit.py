import logging
logger = logging.getLogger(__name__)

class Unit(object):
    """The parent class for Strain, Sample, Sequence, Attribution, """
    def __init__(self):
        self.ignore = ["ignore", "CONFIG"]
        self.parent = None
        self.children = []

    def move(self):
        ## move names. I'm guessing this will need to use self.parent & self.child methods
        pass

    def fix_single(self, name):
        """ try to apply the fix function (as defined in the config) to a single piece of state (name) """
        try:
            setattr(self, name, self.CONFIG["fix_functions"][name](getattr(self, name), logger))
        except KeyError: ## the cleaning function wasn't set
            pass
        except AttributeError: ## the piece of state doesn't exist
            logger.warn("Tried to fix {} but it didn't exist".format(name))

    def fix(self):
        """ apply the fix method to all pieces of state, except those which are in the ignore list """
        for name in vars(self):
            if name not in self.ignore:
                self.fix_single(name)

    def create_single(self, name):
        """ try to apply the create function (as defined in the config) to a single piece of state (name) """
        try:
            v = self.CONFIG["create_functions"][name](self, logger)
            if v:
                setattr(self, name, v)
        except KeyError: ## the cleaning function wasn't set
            pass

    def create(self):
        pass;

    def drop(self):
        ## drop values. This is dangerous - make sure all objects.move() have completed
        pass

    def get_data(self):
        return {k:v for k, v in self.__dict__.iteritems() if k not in self.ignore}
