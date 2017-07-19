from __future__ import print_function  # Python 2/3 compatibility
import boto3
import os
from datetime import date, datetime
import time

dynamodb = boto3.resource('dynamodb')
seconds_in_a_day = 84600


# main handler
# noinspection PyUnusedLocal
def popper_handler(event, context):
    if (event['session']['application']['applicationId'] !=
            os.environ['alexa_skill_id']):
        raise ValueError("Invalid Application ID")

    if event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])


def new_ingestion(intent, user_id):
    """ Adds a new ingestion event based on the pillType.
    :param intent: The intent containing the pillType slot.
    :param user_id: The id of the user for whom to add a new ingestion.
    :return: an appropriate response.
    """
    card_title = intent['name']
    session_attributes = {}
    should_end_session = False
    if 'pillType' in intent['slots']:
        pill_type = intent['slots']['pillType']['value']
        add_ingestion_of(user_id, pill_type)
        session_attributes = {"pillType": pill_type}
        speech_output = "You've just taken your " + \
                        pill_type + \
                        " medicine."
        reprompt_text = "You can say you took your pill by saying, " \
                        "I've just taken my pill."
    else:
        speech_output = "I'm not sure what your medicine type is. " \
                        "Please try again."
        reprompt_text = "I'm not sure what your medicine type is. " \
                        "You can tell me your pillType by saying something like, " \
                        "The cholesterol pill, or, the Crestor pill."
    return build_response(session_attributes,
                          build_speechlet_response(card_title, speech_output, reprompt_text, should_end_session))


def check_last_ingestion(intent, user_id):
    """ Checks whether last ingestion occurred within the last 24 hours.
    :param intent: The intent containing the pillType slot.
    :param user_id: The id of the user for whom to check the last ingestion.
    :return: an appropriate response.
    """

    card_title = intent['name']
    session_attributes = {}
    should_end_session = False
    speech_output = None
    reprompt_text = None

    if 'pillType' in intent['slots']:
        pill_type = intent['slots']['pillType']['value']
        last_ingestion = get_last_ingestion(user_id, pill_type)
        session_attributes = {"pillType": pill_type}
        if not date.fromtimestamp(last_ingestion) == date.today():
            speech_output = "You've already taken your " + \
                            pill_type + \
                            " medicine today."
        else:
            speech_output = "You have not yet taken your " + \
                            pill_type + \
                            " medicine today."
            reprompt_text = "I'm not sure what your medicine type is. " \
                            "You can tell me your pillType by saying something like, " \
                            "The cholesterol pill, or, the Crestor pill."

    return build_response(session_attributes,
                          build_speechlet_response(card_title, speech_output, reprompt_text, should_end_session))


def build_speechlet_response(title, output, reprompt_text, should_end_session):
    return {
        'outputSpeech': {
            'type': 'PlainText',
            'text': output
        },
        'card': {
            'type': 'Simple',
            'title': "SessionSpeechlet - " + title,
            'content': "SessionSpeechlet - " + output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session
    }


def get_welcome_response():
    session_attributes = {}
    card_title = "Welcome"
    speech_output = "Welcome to PillPopper. Please tell me the type of pill."
    reprompt_text = "Please tell me the pill type by saying something like, " \
                    "the pill type is Crestor, or, " \
                    "the cholesterol pill."
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }


# def add_new_pill_type(pill_type):
#     dynamo.add_a_pill_type(pill_type)


def add_ingestion_of(user_id, pill_type):
    today = convert_date_to_string(date.today())
    today_timestamp = time.mktime(datetime.strptime(today, "%Y-%m-%d").timetuple())
    table = dynamodb.Table('ingestions')
    table.update_item(
        Key={
            'user_id': user_id,
            'pill_type': pill_type
        },
        UpdateExpression="set timestamp = :t",
        ExpressionAttributeValues={
            ':t': today_timestamp
        },
        ReturnValues="UPDATED_NEW"
    )


def convert_date_to_string(the_date):
    return str(the_date.year) + '-' + str(the_date.month) + '-' + str(the_date.day)


def get_last_ingestion(user_id, pill_type):
    table = dynamodb.Table('ingestions')
    response = table.get_item(
        Key={
            'user_id': user_id,
            'pill_type': pill_type
        }
    )
    return float(response['Item']['timestamp'])


def handle_session_end_request():
    card_title = "Session Ended"
    speech_output = "Goodbye!"
    # Setting this to true ends the session and exits the skill.
    should_end_session = True
    return build_response({}, build_speechlet_response(
        card_title, speech_output, None, should_end_session))


def on_session_ended(session_ended_request, session):
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    return {
        "message": "Goodbye."
    }


def on_intent(intent_request, session):
    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    user_id = session['user']['userId']
    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    # Dispatch to your skill's intent handlers
    if intent_name == "DidITakePill":
        return check_last_ingestion(intent, user_id)
    elif intent_name == "TookMyPill":
        return new_ingestion(intent, user_id)
    elif intent_name == "AMAZON.HelpIntent":
        return get_welcome_response()
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        return handle_session_end_request()
    else:
        raise ValueError("Invalid intent")
