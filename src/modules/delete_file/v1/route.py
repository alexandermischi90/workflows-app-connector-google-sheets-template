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
    This deletes a Google Sheets file with a given name.
    """
    try:
        # Parse the request
        request = Request(flask_request)
        data = request.data

        # credentials, dict
        credentials = data['google_drive_credentials']

        # initialize connector
        gs_connector = GoogleSheets(credentials)

        # delete file
        file_name = data['file_name']
        gs_connector.delete(file_name)

        # Return results
        return Response(
            data={},
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
    """
    Fetch a list of Google Sheets file names to populate a dynamic dropdown field.
    """
    try:
        request = Request(flask_request)
        data = request.data

        # credentials, dict
        credentials = json.loads(data['form_data']['google_drive_credentials'])

        # initialize connector
        gs_connector = GoogleSheets(credentials)

        # fetch file names
        result = gs_connector.get_file_list()

        # use file_name and no id, bc all operations work with file name (other functions need to be able to work just with file name)
        content_objects = [{
            'content_object_name': 'file_names',
            'data': [{'value': file_name, 'label': file_name} for file_name in result]
        }]
        return Response(data={"content_objects": content_objects})
    except ManagedError as e:
        return Response.error(str(e))
    except Exception as e:
        return Response.error(str(e))
