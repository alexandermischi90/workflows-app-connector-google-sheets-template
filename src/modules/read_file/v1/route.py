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

        # delete file
        file_name = data['file_name']
        url = gs_connector.get_spreadsheet(file_name)

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
    """
    This is the function that goes and fetches the necessary data to populate the possible choices in dynamic form fields.
    For example, if you have a module to delete a contact, you would need to fetch the list of contacts to populate the dropdown
    and give the user the choice of which contact to delete.

    An action's form may have multiple dynamic form fields, each with their own possible choices. Because of this, in the /content route,
    you will receive a list of content_object_names, which are the identifiers of the dynamic form fields. A /content route may be called for one or more content_object_names.

    Every data object takes the shape of:
    {
        "value": "value",
        "label": "label"
    }
    
    Args:
        data:
            form_data:
                form_field_name_1: value1
                form_field_name_2: value2
            content_object_names:
                [
                    {   "id": "content_object_name_1"   }
                ]
        credentials:
            connection_data:
                value: (actual value of the connection)

    Return:
        {
            "content_objects": [
                {
                    "content_object_name": "content_object_name_1",
                    "data": [{"value": "value1", "label": "label1"}]
                },
                ...
            ]
        }
    """
    try:
        request = Request(flask_request)
        data = request.data

        # NO parameter validation (should be validated by the workflow engine itself and not necessary here)

        # write credentials file to temp location - arrives as a str!
        credentials = data['form_data']['google_drive_credentials']
        # ensure correct format
        assert isinstance(credentials, str), "Credentials must be a str"
        tmp_path = '/tmp/credentials.json'
        with open(tmp_path, 'w', encoding='utf-8') as cred_file:
            cred_file.write(credentials)

        # initialize connector
        gs_connector = GoogleSheets(tmp_path)

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
