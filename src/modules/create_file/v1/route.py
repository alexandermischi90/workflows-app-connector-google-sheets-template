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
    This is the function that is executed when you click on "Run" on a workflow that uses this action.
    """
    try:
        # Parse the request
        request = Request(flask_request)

        data = request.data

        # NO parameter validation (should be validated by the workflow engine itself and not necessary here)

        # write credentials file to temp location
        credentials = data['google_drive_credentials']
        # ensure correct format
        assert isinstance(credentials, dict), "Credentials must be a json"
        tmp_path = '/tmp/credentials.json'
        with open(tmp_path, 'w', encoding='utf-8') as cred_file:
            json.dump(credentials, cred_file)

        # initialize connector
        gs_connector = GoogleSheets(tmp_path)

        # create empty file
        file_name = data['file_name']
        url = gs_connector.create(file_name, emails=['alexander.mischi@gmail.com'])

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
