class BuildFailed(Exception):
    pass

def get_subclasses(supercls):
    for cls in supercls.__subclasses__():
        if cls is object:
            continue
        yield cls
        for subclass in get_subclasses(cls):
            yield subclass

def make_choice_list(iterable):
    return [(item, item) for item in iterable]
