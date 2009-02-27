from django import template

register = template.Library()
@register.tag(name='highlight')
def do_highlight(parser, token):
    nodelist = parser.parse(('endhighlight',))
    parser.delete_first_token()
    return HighlightNode(nodelist)

class HighlightNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        return "<pre>\n%s\n</pre>" % output
