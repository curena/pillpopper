from __future__ import print_function  # Python 2/3 compatibility

import json
import logging
import os
import time
from datetime import date, datetime

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.client('dynamodb')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# main handler
# noinspection PyUnusedLocal
def popper_handler(event, context):
    logger.info('Alexa Skill ID: {}'.format(os.environ['alexa_skill_id']))
    if (event['session']['application']['applicationId'] !=
            os.environ['alexa_skill_id']):
        raise ValueError("Invalid Application ID")

    logger.info("Request Type: {}".format(event['request']['type']))

    if 'intent' in event['request']:
        logger.info("Intent Name: {}".format(event['request']['intent']['name']))

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'])
    if event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])


def new_ingestion(intent, user_id, directive):
    """ Adds a new ingestion event based on the pillType.
    :param directive: Notifies Alexa whether or not to continue asking.
    :param intent: The intent containing the pillType slot.
    :param user_id: The id of the user for whom to add a new ingestion.
    :return: an appropriate response.
    """
    card_title = intent['name']
    session_attributes = {}
    should_end_session = True
    directive_to_return = None

    if 'pillType' in intent['slots'] and 'value' in intent['slots']['pillType']:
        pill_type_value = intent['slots']['pillType']['value']
        logger.info("pillType is {}".format(pill_type_value))
        session_attributes = {"pillType": pill_type_value}
        if took_pill_today(user_id, pill_type_value):
            speech_output = "Wait! You've already taken your " + pill_type_value + " medicine today."
        else:
            add_ingestion_of(user_id, pill_type_value)
            speech_output = "Ok, I've recorded that you just took your " + pill_type_value + " medicine."
    else:
        speech_output = None
        should_end_session = False
        directive_to_return = directive
        logger.info("We do NOT have a pillType value.")

    return build_response(session_attributes,
                          build_speechlet_response(card_title, speech_output, None, should_end_session,
                                                   directive_to_return))


def took_pill_today(user_id, pill_type_value):
    last_ingestion = get_last_ingestion(user_id, pill_type_value)
    if last_ingestion is not None:
        return date.fromtimestamp(last_ingestion) == date.today()
    else:
        return False


def check_last_ingestion(intent, user_id, directive):
    """ Checks whether last ingestion occurred within the last 24 hours.
    :param directive: Notifies Alexa whether or not to continue asking.
    :param intent: The intent containing the pillType slot.
    :param user_id: The id of the user for whom to check the last ingestion.
    :return: an appropriate response.
    """

    card_title = intent['name']
    session_attributes = {}
    should_end_session = True
    directive_to_return = None

    if 'pillType' in intent['slots'] and 'value' in intent['slots']['pillType']:
        pill_type_value = intent['slots']['pillType']['value']
        logger.info("pillType value is {}".format(pill_type_value))
        last_ingestion = get_last_ingestion(user_id, pill_type_value)

        if last_ingestion is not None:
            session_attributes = {"pillType": pill_type_value}
            if date.fromtimestamp(last_ingestion) == date.today():
                speech_output = "You've already taken your " + \
                                pill_type_value + \
                                " medicine today."
            else:
                speech_output = "You have not yet taken your " + \
                                pill_type_value + \
                                " medicine today."
        else:
            speech_output = "There is no entry for that particular medicine type."
    else:
        speech_output = None
        should_end_session = False
        directive_to_return = directive
        logger.info("We do NOT have a pillType value.")

    return build_response(session_attributes,
                          build_speechlet_response(card_title, speech_output, None, should_end_session,
                                                   directive_to_return))


def build_speechlet_response(title, output, reprompt_text, should_end_session, directive):
    output_field = None
    reprompt_field = None

    if output is not None:
        output_field = {
            'type': 'PlainText', 'text': output
        }

    if reprompt_text is not None:
        reprompt_field = {
            'outputSpeech': {
                'type': 'PlainText', 'text': reprompt_text
            }
        }

    if directive is None:
        speechlet_response = {
            'outputSpeech': output_field,
            'card': {
                'type': 'Simple',
                'title': "SessionSpeechlet - " + title,
                'content': "SessionSpeechlet - " + str(output)
            },
            'reprompt': reprompt_field,
            'shouldEndSession': should_end_session
        }
    else:
        speechlet_response = {
            'card': {
                'type': 'Simple',
                'title': "SessionSpeechlet - " + title,
                'content': "SessionSpeechlet - " + str(output)
            },
            'shouldEndSession': should_end_session,
            'directives': [directive]
        }
    logger.info('Speechlet Response: {}'.format(speechlet_response))

    return speechlet_response


def get_welcome_response(directive):
    session_attributes = {}
    card_title = "Welcome"
    speech_output = "Welcome to PillPopper. Please tell me what you'd like to do. " \
                    "You can say, 'I just took my pill', or, 'Did I take my pill today?'"
    reprompt_text = "I'm not quite sure what you meant by that. " \
                    "You can say, 'I just took my pill', or, 'Did I take my pill today?'"
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session, directive))


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }


def add_ingestion_of(user_id, pill_type):
    today = convert_date_to_string(date.today())
    today_timestamp = time.mktime(datetime.strptime(today, "%Y-%m-%d").timetuple())
    item_value = {
        'N': str(today_timestamp)
    }

    try:
        dynamodb.update_item(
            TableName='Ingestions',
            Key={
                'user_id': {'S': str(user_id)},
                'pill_type': {'S': str(pill_type)}
            },
            UpdateExpression="set ingestion_timestamp = :t",
            ExpressionAttributeValues={
                ':t': item_value
            },
            ReturnValues="UPDATED_NEW"
        )
    except ClientError as e:
        logger.error("Error updating item. {}".format(e.response['Error']['Message']))


def convert_date_to_string(the_date):
    return str(the_date.year) + '-' + str(the_date.month) + '-' + str(the_date.day)


def get_last_ingestion(user_id, pill_type):
    item = None
    try:
        response = dynamodb.get_item(
            TableName='Ingestions',
            Key={
                'user_id': {'S': str(user_id)},
                'pill_type': {'S': str(pill_type)}
            }
        )
        logger.info("Response: {}".format(json.dumps(response, indent=4)))
        if 'Item' in response:
            item = response['Item']
    except ClientError as e:
        logger.error("Error finding item. {}".format(e.response['Error']['Message']))

    if item is not None:
        return float(item['ingestion_timestamp']['N'])
    else:
        return None


def handle_session_end_request():
    card_title = "Session Ended"
    speech_output = "Goodbye!"
    # Setting this to true ends the session and exits the skill.
    should_end_session = True
    return build_response({}, build_speechlet_response(
        card_title, speech_output, None, should_end_session, None))


def on_session_ended(session_ended_request, session):
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    return {
        "message": "Goodbye."
    }


def on_launch(launch_request, session):
    """ Called when the user launches the skill without specifying what they
    want
    """

    print("on_launch requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # Dispatch to your skill's launch
    return get_welcome_response(None)


def on_intent(intent_request, session):
    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    user_id = session['user']['userId']
    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']
    dialog_state = intent_request['dialogState']
    directive = None

    if dialog_state != 'COMPLETED':
        directive = {
            "type": "Dialog.Delegate"
        }

    # Dispatch to your skill's intent handlers
    if intent_name == "DidITakePill":
        return check_last_ingestion(intent, user_id, directive)
    elif intent_name == "TookMyPill":
        return new_ingestion(intent, user_id, directive)
    elif intent_name == "AMAZON.HelpIntent":
        logger.info("Help intent executed.")
        return get_welcome_response(directive)
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        logger.info("Cancel or Stop intent executed.")
        return handle_session_end_request()
    else:
        raise ValueError("Invalid intent")
