from PPA.Template.Cook import Repeat, pare

def makeBreaks(brick, text):
    return text.replace('\n', '<br>')

def makeSubstitutions(brick, text, substitutionsStream="substitutions"):
    """Assumes substitutionsStream's items have id, header and footer
    attributes, substitutes header instead of <id> and footer instead of
    </id>"""
    
    stream = brick.site.retrieveStream(substitutionsStream)
    for item in stream:
        text = text.replace('<%s>' % item.id, item.header)
        text = text.replace('</%s>' % item.id, item.footer)
    return text

def numbered(num, variants):
    if not num % 10 or 10 < num % 100 < 20:
        return variants[2]
    elif num % 10 == 1:
        return variants[0]
    elif num % 10 in (2, 3, 4):
        return variants[1]
    else:
        return variants[2]
