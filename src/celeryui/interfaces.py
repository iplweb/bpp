from zope.interface import interface


class IWebTask(interface.Interface):
    """A task, that can be displayed on a web UI -- contains attributes and
    methods, that allow rendering of user-readable output.
    """
    title = interface.Attribute("Title of this task")
    slug = interface.Attribute("Slug")
    readable_arguments = interface.Method(
        "Get string containing readable arguments")


class IReportMaker(interface.Interface):
    """Something, that produces reports.
    """

    perform = interface.Method("""
        Function to run to produce the report.""")


class IReport(interface.Interface):
    """A long-running background task class, with description, title and
    parameters.
    """
    function = interface.Attribute("Function of this report")
    arguments = interface.Attribute("Arguments of this report")

