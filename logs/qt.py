class qt:
    def __init__(self):
        print(__name__)

    def p(self):
        print(__name__)


print(__name__)
q = qt()
q.p()