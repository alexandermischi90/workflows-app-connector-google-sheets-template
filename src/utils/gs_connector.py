from __future__ import annotations
import string
from itertools import product
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.http import MediaFileUpload
import io
from google.oauth2.service_account import Credentials


ALPHABET = [c for c in string.ascii_uppercase] + [c1 + c2 for c1, c2 in product(string.ascii_uppercase, string.ascii_uppercase)] + [c1 + c2 + c3 for c1, c2, c3 in product(string.ascii_uppercase, string.ascii_uppercase, string.ascii_uppercase)]


class GoogleSheets:
    INSTANCES = {}

    def __init__(self, json_creds_file):
        self.creds = Credentials.from_service_account_file(json_creds_file, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        self._fix_cryptography()
        self.drive_service = build('drive', 'v3', credentials=self.creds, cache_discovery=False)
        self.sheet_service = build('sheets', 'v4', credentials=self.creds, cache_discovery=False)

    def _fix_cryptography(self):
        # fix for cryptography changes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes
        signer = self.creds._signer

        def fixed_sign(message):
            # Force both constants to be instances
            pad = padding.PKCS1v15()
            algo = hashes.SHA256()
            return signer._key.sign(message, pad, algo)

        signer.sign = fixed_sign

    def create(self, file_name: str, emails: list[str]) -> str:
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
        # Search for the file by name
        query = f"name='{file_name}' and mimeType='application/vnd.google-apps.spreadsheet'"
        response = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = response.get('files', [])

        if not files:
            raise FileNotFoundError(f"No file found with the name: {file_name}")

        for file in files:
            file_id = file.get('id')
            self.drive_service.files().delete(fileId=file_id).execute()

    def rename(self, old_file_name: str, new_file_name: str) -> None:
        # Search for the file by name
        query = f"name='{old_file_name}' and mimeType='application/vnd.google-apps.spreadsheet'"
        response = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = response.get('files', [])

        if not files:
            raise FileNotFoundError(f"No file found with the name: {old_file_name}")

        for file in files:
            file_id = file.get('id')
            # Update the file's name
            updated_metadata = {'name': new_file_name}
            self.drive_service.files().update(fileId=file_id, body=updated_metadata).execute()

    def get_file_list(self) -> list[str]:
        results = self.drive_service.files().list(
            pageSize=100,
            fields="nextPageToken, files(id, name)",
            q="mimeType='application/vnd.google-apps.spreadsheet'"
        ).execute()
        items = results.get('files', [])
        return [item['name'] for item in items]

    def get_spreadsheet(self, file_name: str) -> dict:
        # Search for the file by name
        query = f"name='{file_name}' and mimeType='application/vnd.google-apps.spreadsheet'"
        response = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = response.get('files', [])
        if not files:
            raise FileNotFoundError(f"No file found with the name: {file_name}")
        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{files[0]['id']}/edit"
        spreadsheet_id = self.get_sheet_id_from_url(spreadsheet_url)
        spreadsheet = self.sheet_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

        # get values
        values = {}
        ranges = [f"{sheet_data['properties']['title']}!A1:ZZ1000" for sheet_data in spreadsheet.get('sheets', [])]
        result = self.sheet_service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id, ranges=ranges
        ).execute().get('valueRanges', [])

        for s_idx, sheet_data in enumerate(spreadsheet.get('sheets', [])):
            title = sheet_data['properties']['title']
            if title == 'Dashboard':
                continue
            values[title] = {}
            # Fetch values for each sheet
            # range_name = f"{title}!A1:ZZ1000"  # Adjust range as needed
            # Fetch values for each sheet
            # start = time.time()
            # result = self.sheet_service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
            # print('time to get values', title, time.time() - start)
            sheet_values = result[s_idx].get("values", [])

            # Write values to the Excel sheet
            for row_idx, row_data in enumerate(sheet_values):
                for col_idx, cell_value in enumerate(row_data):
                    row_number = row_idx + 1
                    col_name = ALPHABET[col_idx]
                    coord = f"{col_name}{row_number}"
                    values[title][coord] = cell_value

        # transform
        return {
            'name': spreadsheet['properties']['title'],
            'url': spreadsheet_url,
            'id': spreadsheet_id,
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

    def download_values(self, spreadsheet_url: str):
        from python_core.spreadsheets.scan import ALPHABET
        spreadsheet_id = self.get_sheet_id_from_url(spreadsheet_url)
        spreadsheet = self.sheet_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

        # functions = {}
        # kwargs = {}
        values = {}
        ranges = [f"{sheet_data['properties']['title']}!A1:ZZ1000" for sheet_data in spreadsheet.get('sheets', [])]
        result = self.sheet_service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id, ranges=ranges
        ).execute().get('valueRanges', [])
        # print(result)
        for s_idx, sheet_data in enumerate(spreadsheet.get('sheets', [])):
            title = sheet_data['properties']['title']
            if title == 'Dashboard':
                continue
            values[title] = {}
            # Fetch values for each sheet
            # range_name = f"{title}!A1:ZZ1000"  # Adjust range as needed
            # Fetch values for each sheet
            # start = time.time()
            # result = self.sheet_service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
            # print('time to get values', title, time.time() - start)
            sheet_values = result[s_idx].get("values", [])

            # Write values to the Excel sheet
            for row_idx, row_data in enumerate(sheet_values):
                for col_idx, cell_value in enumerate(row_data):
                    row_number = row_idx + 1
                    col_name = ALPHABET[col_idx]
                    coord = f"{col_name}{row_number}"
                    values[title][coord] = {
                        "value": cell_value,
                        "row_idx": row_number,
                        "col_idx": col_idx + 1,
                    }
        return values

    def download_as_excel(self, spreadsheet_url: str, output_filename: str):
        # Create a request
        spreadsheet_id = self.get_sheet_id_from_url(spreadsheet_url)
        request = self.drive_service.files().export_media(fileId=spreadsheet_id, mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')  # noqa
        # Download the file
        fh = io.FileIO(output_filename, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

    @staticmethod
    def get_sheet_id_from_url(spreadsheet_url):
        return spreadsheet_url.split('/d/')[1].split('/')[0]

    def update_cell(self, spreadsheet_url, worksheet_title, cell_address, value):
        # Update the cell
        body = {
            'values': [[value]]
        }
        spreadsheet_id = self.get_sheet_id_from_url(spreadsheet_url)
        result = self.sheet_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{worksheet_title}!{cell_address}',
            valueInputOption='USER_ENTERED',
            body=body).execute()

        return result


if __name__ == '__main__':
    # test the connector with google drive credentials and a spreadsheet name
    connector = GoogleSheets('google-drive-credentials.json')
    link = 'https://docs.google.com/spreadsheets/d/1itJXtO2d9gVH35DvuRsTULHEAA_PrW6Z9OFCx5wbWZI/edit#gid=1157634834'
    link = 'https://docs.google.com/spreadsheets/d/10Eh4ex59NRLWYdERaznGXjZ36FC2SS3kohumVpkSiGc/edit?gid=1601405314#gid=1601405314'
    # print(connector.get_sheet_dfs(link))
    # dfs = connector.get_sheet_dfs('https://docs.google.com/spreadsheets/d/1itJXtO2d9gVH35DvuRsTULHEAA_PrW6Z9OFCx5wbWZI/edit?usp=sharing')
    # print(dfs)
    # connector.update_cell('Cover', 'A1', 'Hello World')
    # sheet_data = connector.get_spreadsheet(link)
    # overview_sheet_id = [data['id'] for data in sheet_data['sheets'] if data['name'] == '1_Overview'][0]
    # connector.download_as_pdf(link, Path(__file__).parent / 'test.pdf', sheet_id=overview_sheet_id)
    # upload test file
    # test_file = Path('tests/files/financial_model.xlsx')
    # assert test_file.exists()
    # file_id = connector.upload_excel(test_file)
    # print(file_id)
    # connector.screenshot(test_file, ['1_Overview', 'Budget'])
    # screenshot_browser(link)
    # connector.download_as_excel(link, Path(__file__).parent / 'test.xlsx')
    print(connector.download_values(link))
    # connect to dfs
