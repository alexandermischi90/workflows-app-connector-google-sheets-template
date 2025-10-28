import json
import traceback
from flask import request as flask_request
from workflows_cdk import Response, Request, ManagedError
from datetime import datetime
from src.utils.gs_connector import GoogleSheets

from main import router


@router.route("/execute", methods=["GET", "POST"])
def execute():
    """
    create an empty Google Sheets file with the given name and optionally share it with an email.
    """
    try:
        # Parse the request
        request = Request(flask_request)

        data = request.data

        # credentials, dict
        credentials = data['google_drive_credentials']

        # initialize connector
        gs_connector = GoogleSheets(credentials)

        # create empty file
        file_name = data['file_name']
        email = data.get('email')
        url = gs_connector.create(file_name, emails=[email] if email else [])

        # Return results
        return Response(
            data={'file_name': file_name, 'url': url},
            metadata={
                "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": f"Created file '{file_name}' successfully."
            }
        )
    except ManagedError as e:
        return Response.error(str(e))
    except Exception as e:
        return Response.error(str(e))


@router.route("/content", methods=["GET", "POST"])
def content():
    # empty content_objects as no dynamic fields are needed
    return Response(data={"content_objects": []})
