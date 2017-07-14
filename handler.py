import boto3

dynamo = boto3.resource('dynamodb')


# main handler
def popper_handler(event, context):
    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": event
    }

    return build_response()


def build_response():


    hello = "foo"
