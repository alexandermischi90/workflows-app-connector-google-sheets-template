# Stacksync Google Sheets Connector

## How do you connect Google Sheets with Stacksync?

In order to connect Google Sheets with Stacksync, you need to create a Google Service Account and provide the credentials to the connector. Follow these steps:
1. **Create a Google Cloud Project**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a new project or select an existing one.
2. **Enable the Google Sheets API and Google Drive API**:
   - In the Cloud Console, navigate to "APIs & Services" > "Library".
   - Search for "Google Sheets API" and "Google Drive API", and enable both APIs for your project.
3. **Create a Service Account**:
   - Go to "APIs & Services" > "Credentials".
    - Click on "Create Credentials" and select "Service Account".
    - Fill in the required details and click "Create".
4. **Create and Download Service Account Key**:
    - After creating the service account, go to the "Keys" tab.
    - Click on "Add Key" > "Create New Key".
    - Select "JSON" as the key type and click "Create". A JSON file will be downloaded to your computer.

## What modules are included?
This connector template includes the following modules:

### Create File
Create a new (empty) Google Sheet file in your Google Drive.

### Read File
Read data from an existing Google Sheet file. For now JSON is the only supported output format.

### Update File
Currently only update operation supported is a 'Rename File' operation.
'Update Cell Value' is already implemented in the utils/gs_connector.py and can be used to implement further update operations.

### Delete File
Delete an existing Google Sheet file from your Google Drive.


