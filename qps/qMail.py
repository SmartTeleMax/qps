# $Id: qMail.py,v 1.3 2004/11/16 12:06:51 corva Exp $

'''Mail utilities'''


import os, types, logging, smtplib, email, email.Message, email.MIMEText, \
       email.Utils, email.Header
import qps
logger = logging.getLogger(__name__)

# i cant remember why do we have to patch email module configuration
# but make thing like that somewhere in your code if you are going to
# use charsets not listed in email module.
# email.Charset.add_charset('koi8-r', email.Charset.BASE64, None, None)


# senders

class Sender:
    '''Base class for email senders'''

    def __init__(self, **kwargs):
        "Updates default configuration"
        self.__dict__.update(kwargs)

    def send(self, message):
        "Sends message (inst of email.Message)"
        raise NotImplementedError # this is abstract class and abstract method


class SendmailSender(Sender):
    '''Sendmail sender'''

    path = "/usr/sbin/sendmail"
    options = ""

    def send(self, message):
        addr = email.Utils.parseaddr(message['to'])[1]
        logger.info('Sending mail to %s', addr)

        sendmail = os.popen(
            "%s %s '%s'" % (self.path, self.options, addr),
            'w'
            )
        sendmail.write(message.as_string())
        sendmail.close()


class SMTPSender(Sender):
    '''SMTP sender'''

    smtpClass = smtplib.SMTP # SMTP class
    host = "localhost"
    port = 25

    def send(self, message):
        addr = email.Utils.parseaddr(message['to'])[1]
        logger.info('Sending mail to %s', addr)

        smtp = self.smtpClass(self.host, self.port)
        smtp.connect()
        smtp.sendmail(message['from'], addr, message.as_string())
        smtp.close()


# composers

def formataddr(addr, charset):
    "Formats addresses, encodes realnames with charset and keeps emails as is"

    realname, addr = email.Utils.parseaddr(addr)
    try:
        type(realname) == str and realname.decode('us-ascii')
        type(realname) == unicode and realname.encode('us-ascii')
    except UnicodeError:
        realname = email.Header.Header(realname, charset).encode()
    return email.Utils.formataddr((realname, addr))

                
class Composer:
    charset = 'ascii' # message charset
    contentType = 'text/plain'
    # default headers, appended to all composed messages
    defaultHeaders = {
        'User-Agent': "qps.qMail/%s" % qps.__version__
        }
    messageClass = email.Message.Message # message class

    def __init__(self, **kwargs):
        "Updates default configuration"
        self.__dict__.update(kwargs)

    def compose(self, From, To, body, **headers):
        '''Takes message body and headers as named params,
        replace "-" with "_" in headers names. Returns email.Message.Message
        object'''

        # message body have to be string
        body = isinstance(body, unicode) and body.encode(self.charset) or body
        
        message = self.messageClass()
        message.set_payload(body, self.charset)
        message.set_type(self.contentType)

        message['To'] = formataddr(To, self.charset)
        message['From'] = formataddr(From, self.charset)

        h = self.defaultHeaders.copy()
        h.update(headers)
        for name, value in h.items():
            name = name.replace('_', '-')
            try:
                type(value) == str and value.decode('us-ascii')
                type(value) == unicode and value.encode('us-ascii')
            except UnicodeError:
                # i18n header is really needed
                message[name] = email.Header.Header(value, self.charset)
            else:
                message[name] = str(value)

        return message


# functions

def send(From, To, subject, body, composer=Composer(),
         sender=SendmailSender()):
    message = composer.compose(From, To, body, Subject=subject)
    return sender.send(message)
 
def send_huge_mail(From, To, subject, body, composer = Composer(),
                   sender=SendmailSender(options="-odq")):
    message = composer.compose(From, To, body, Subject=subject,
                               Precedence='bulk')
    return sender.send(message)
