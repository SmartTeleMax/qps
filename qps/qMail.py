# $Id: qMail.py,v 1.6 2004/03/16 15:48:21 ods Exp $

'''Mail utilities'''


import os, types, logging, smtplib, email, email.Message, email.MIMEText
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
        logger.info('Sending mail to %s', message['to'])

        sendmail = os.popen(
            "%s %s '%s'" % (self.path, self.options, message['to']),
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
        logger.info('Sending mail to %s', message['to'])

        smtp = self.smtpClass(self.host, self.port)
        smtp.connect()
        smtp.sendmail(message['from'], message['to'], message.as_string())
        smtp.close()

# composers

class Composer:
    '''Base class for all composers'''

    charset = 'ascii' # message charset
    defaultHeaders = {} # default headers, appended to all composed messages
    messageClass = email.Message.Message # message class

    def __init__(self, **kwargs):
        "Updates default configuration"
        self.__dict__.update(kwargs)

    def compose(self, body, Subject, **kwargs):
        '''Takes message body and headers as named params,
        replace "-" with "_" in headers names. Returns email.Message.Message
        object'''
        if self.charset:
            # subject is an internationalized header, should be quoted
            from email.Header import Header
            Subject = Header(Subject, self.charset)
            message = self.messageClass(body, _charset=self.charset)
        else:
            message = self.messageClass(body)

        headers = self.defaultHeaders.copy()
        headers.update(kwargs)
        for name, value in headers.items():
            message[name.replace('_', '-')] = value

        message['Subject'] = Subject

        return message

class NonMultipartComposer(Composer):
    '''Non Multipart messages composer'''

    messageClass = email.MIMEText.MIMEText

# functions
#

def send(mfrom, mto, subject, body, composer=NonMultipartComposer(),
         sender=SendmailSender()):
    message = composer.compose(body, From=mfrom, To=mto, Subject=subject)
    return sender.send(message)

 
def send_huge_mail(mfrom, mto, subject, body):
    composer = NonMultipartComposer()
    sender = SendmailSender(options="-odq")

    message = composer.compose(body, From=mfrom, To=mto, Subject=subject,
                               Precedence='bulk')
    return sender.send(message)
