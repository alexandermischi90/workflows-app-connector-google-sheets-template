# std packages
import json
import string
from pathlib import Path
from itertools import product
from typing import Any
# google packages
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials


# column naming for google sheets (A, B, ..., Z, AA, AB, ..., ZZ, AAA, AAB, ...)
ALPHABET = [c for c in string.ascii_uppercase] + [c1 + c2 for c1, c2 in product(string.ascii_uppercase, string.ascii_uppercase)] + [c1 + c2 + c3 for c1, c2, c3 in product(string.ascii_uppercase, string.ascii_uppercase, string.ascii_uppercase)]


class GoogleSheets:
    def __init__(self, credentials: dict):
        """authenticate and initialize the Google Sheets and Drive API clients with the provided credentials.
        Args:
            credentials (dict): service account credentials as a dictionary.
        """
        # empty -> use own credentials
        if credentials == {'type': 'mock'}:
            json_creds_file = 'credentials.json'
        else:
            json_creds_file = '/tmp/credentials.json'
            with open(json_creds_file, 'w', encoding='utf-8') as cred_file:
                json.dump(credentials, cred_file)
        self.creds = Credentials.from_service_account_file(json_creds_file, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        self._fix_cryptography()
        self.drive_service = build('drive', 'v3', credentials=self.creds, cache_discovery=False)
        self.sheet_service = build('sheets', 'v4', credentials=self.creds, cache_discovery=False)

    def create(self, file_name: str, emails: list[str]) -> str:
        """create a new Google Sheets file in Google Drive and share it with the specified email addresses.

        Args:
            file_name (str): _description_
            emails (list[str]): _description_

        Returns:
            str: _description_
        """
        file_metadata = {
            'name': file_name,
            'mimeType': 'application/vnd.google-apps.spreadsheet',  # Google Sheets MIME type
            'copyRequiresWriterPermission': False,
            'writersCanShare': True,
            'viewersCanCopyContent': True,
        }
        file = self.drive_service.files().create(body=file_metadata, fields='id').execute()
        file_id = file.get('id')
        # add permissions to emails given
        for email in emails:
            permission = {
                'type': 'user',
                'role': 'writer',  # or 'reader' if you only want view access
                'emailAddress': email,
            }
            self.drive_service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id',
                sendNotificationEmail=False  # prevent Google from emailing each recipient
            ).execute()
        return f'https://docs.google.com/spreadsheets/d/{file_id}/edit'

    def delete(self, file_name: str) -> None:
        """delete ALL google sheets files with the given name.

        Args:
            file_name (str): _description_

        Raises:
            FileNotFoundError: _description_
        """
        # Search for the file by name
        query = f"name='{file_name}' and mimeType='application/vnd.google-apps.spreadsheet'"
        response = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = response.get('files', [])

        if not files:
            raise FileNotFoundError(f"No file found with the name: {file_name}")

        for file in files:
            file_id = file.get('id')
            self._delete_file_by_id(file_id)

    def rename(self, old_file_name: str, new_file_name: str) -> None:
        """rename a Google Sheets file. If multiple files with the same name exist, only the first one found will be renamed.

        Args:
            old_file_name (str): _description_
            new_file_name (str): _description_
        """
        file_id = self._get_file_id(old_file_name)
        # Update the file's name
        updated_metadata = {'name': new_file_name}
        self.drive_service.files().update(fileId=file_id, body=updated_metadata).execute()

    def get_file_list(self) -> list[str]:
        """get the list of Google Sheets files in Google Drive - all that are visible by your service account.

        Returns:
            list[str]: _description_
        """
        results = self.drive_service.files().list(
            pageSize=100,
            fields="nextPageToken, files(id, name)",
            q="mimeType='application/vnd.google-apps.spreadsheet'",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        items = results.get('files', [])
        return [item['name'] for item in items]

    def get_spreadsheet(self, file_name: str, format: str = 'JSON') -> dict | str:
        """get the content of a Google Sheets file by its name.

        Args:
            file_name (str): _description_

        Raises:
            FileNotFoundError: _description_

        Returns:
            dict: _description_
        """
        file_id = self._get_file_id(file_name)
        spreadsheet_url = self._get_spreadsheet_url(file_id)
        spreadsheet = self.sheet_service.spreadsheets().get(spreadsheetId=file_id).execute()

        # get data
        if format == 'JSON':
            values = {}
            ranges = [f"{sheet_data['properties']['title']}!A1:ZZ1000" for sheet_data in spreadsheet.get('sheets', [])]
            result = self.sheet_service.spreadsheets().values().batchGet(
                spreadsheetId=file_id, ranges=ranges
            ).execute().get('valueRanges', [])

            for s_idx, sheet_data in enumerate(spreadsheet.get('sheets', [])):
                title = sheet_data['properties']['title']
                values[title] = {}
                sheet_values = result[s_idx].get("values", [])

                # Write values to the Excel sheet
                for row_idx, row_data in enumerate(sheet_values):
                    for col_idx, cell_value in enumerate(row_data):
                        row_number = row_idx + 1
                        col_name = ALPHABET[col_idx]
                        coord = f"{col_name}{row_number}"
                        values[title][coord] = cell_value

            # transform
            data = {
                'name': spreadsheet['properties']['title'],
                'url': spreadsheet_url,
                'id': file_id,
                'sheets': [
                    {
                        'name': sheet['properties']['title'],
                        'id': sheet['properties']['sheetId'],
                        'index': sheet['properties']['index'],
                        'nb_rows': sheet['properties']['gridProperties']['rowCount'],
                        'nb_cols': sheet['properties']['gridProperties']['columnCount'],
                        'tab_color': sheet['properties']['tabColor'],
                        'cells': values.get(sheet['properties']['title'], {}),
                    }
                    for sheet in sorted(spreadsheet['sheets'], key=lambda x: x['properties']['index'])
                ],
            }
        else:
            raise ValueError(f"Unsupported format: {format}")
        return data

    def update_cell(self, file_name: str, worksheet_title: str, cell_address: str, value: Any):
        """update a specific cell in a Google Sheets file.

        Args:
            file_name (str): _description_
            worksheet_title (str): _description_
            cell_address (str): _description_
            value (Any): _description_

        Returns:
            _type_: _description_
        """
        # get spreadsheet url
        file_id = self._get_file_id(file_name)
        # Update the cell
        body = {
            'values': [[value]]
        }
        spreadsheet_id = self.get_sheet_id_from_url(file_id)
        result = self.sheet_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{worksheet_title}!{cell_address}',
            valueInputOption='USER_ENTERED',
            body=body).execute()

        return result

    # helper functions

    def _fix_cryptography(self):
        """there is a conflict with google-auth and cryptography library versions that causes signing to fail.
        It seems to reoccur no matter the version pinned. The fix is a stable monkey patch that forces the use of PKCS1v15 and SHA256.
        """
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes
        signer = self.creds._signer

        def fixed_sign(message):
            # Force both constants to be instances, not classes
            pad = padding.PKCS1v15()
            algo = hashes.SHA256()
            return signer._key.sign(message, pad, algo)

        signer.sign = fixed_sign

    def _get_file_id(self, file_name: str) -> str:
        """get the file ID of a Google Sheets file by its name. Return the id of the FIRST match.

        Args:
            file_name (str): _description_

        Returns:
            str: _description_
        """
        # Search for the file by name
        query = f"name='{file_name}' and mimeType='application/vnd.google-apps.spreadsheet'"
        response = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = response.get('files', [])

        if not files:
            raise FileNotFoundError(f"No file found with the name: {file_name}")
        return files[0].get('id')

    def _delete_file_by_id(self, file_id: str) -> None:
        """delete a Google Sheets file by its file ID.

        Args:
            file_id (str): _description_
        """
        self.drive_service.files().delete(fileId=file_id).execute()

    def _get_spreadsheet_url(self, file_id: str) -> str:
        """get the spreadsheet url of a Google Sheets file by its id.

        Args:
            file_name (str): _description_

        Raises:
            FileNotFoundError: _description_

        Returns:
            str: _description_
        """
        return f"https://docs.google.com/spreadsheets/d/{file_id}/edit"
