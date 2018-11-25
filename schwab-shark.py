from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import base64
import datetime
import glob
import os
import sendgrid
from sendgrid.helpers.mail import Email, Content, Mail, Attachment, Personalization
import sys
import time

LOGIN_URL="https://lms.schwab.com/Login?ClientId=schwab-secondary&Region=&RedirectUri=https://client.schwab.com/Login/Signon/AuthCodeHandler.ashx&StartInSetId=1"

def main():
    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))

    # grab these from args -- we can do better parsing this
    username = sys.argv[1]
    password = sys.argv[2]

    # we can probably take this in but this is fine for now
    download_directory_base="/var/tmp/schwab-shark"
    if not os.path.exists(download_directory_base):
        os.makedirs(download_directory_base)

    user_directory="{}/{}".format(download_directory_base, username)
    if not os.path.exists(user_directory):
        os.makedirs(user_directory)

    download_file(username, password, user_directory)

    list_of_files = glob.glob("{}/*.CSV".format(user_directory))
    latest_file = max(list_of_files, key=os.path.getctime)

    with open(latest_file,'rb') as f:
        data = f.read()
        f.close()
    encoded = base64.b64encode(data).decode()

    attachment = Attachment()
    attachment.content = encoded
    attachment.type = "application/csv"
    attachment.filename = "{}-{}.csv".format(username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    attachment.disposition = "attachment"
    attachment.content_id = "Example Content ID"

    mail = build_email_for(username)
    mail.add_attachment(attachment)
    try:
        response = sg.client.mail.send.post(request_body=mail.get())
    except urllib.HTTPError as e:
        print(e.read())
        exit()

def build_email_for(username):
    mail = Mail()
    mail.from_email = Email("hammerhead@schwab-shark.io", "Mr. Hammerhead")
    mail.subject = "Schwab Shark[{}] - {}".format(username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

    personalization = Personalization()
    personalization.add_to(Email("you@email.com", "You"))
    mail.add_personalization(personalization)

    mail.add_content(Content("text/html", "Report attached"))

    return mail

def download_file(username, password, destination):
    # set things up so we don't have to deal with download popups
    options = Options()
    options.add_experimental_option("prefs", {
        "download.default_directory": destination,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })
    browser = webdriver.Chrome(chrome_options=options)
    browser.get(LOGIN_URL)

    main_window = browser.window_handles[0]
    username_field = browser.find_element_by_id("LoginId") #username form field
    password_field = browser.find_element_by_id("Password") #password form field

    # provide this via the command line
    username_field.send_keys(username)
    password_field.send_keys(password)

    submitButton = browser.find_element_by_id("LoginSubmitBtn")
    submitButton.click()

    # wait for shit to load
    time.sleep(5)

    position_link = browser.find_element_by_link_text("Positions")
    position_link.click()

    time.sleep(5)

    export_link = browser.find_element_by_link_text("Export")
    export_link.click()

    time.sleep(5)

    # this is the popup shit
    window_after = browser.window_handles[1]
    browser.switch_to_window(window_after)
    agree_link = browser.find_element_by_link_text("OK")
    agree_link.click()
    time.sleep(5)
    browser.switch_to_window(main_window)
    time.sleep(5)
    browser.quit()

if __name__== "__main__":
  main()
