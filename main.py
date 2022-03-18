from pathlib import Path, PosixPath
from datetime import datetime
import ctypes
import sys
import json
import hashlib
import shutil
import logging


from bs4 import BeautifulSoup
import requests

debug_mode:bool = True

# SET IN DEBUG MODE
if debug_mode:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.ERROR)


# used in database
IMAGES: str = "IMAGES"

# used to detrmine Documets directory path
USER_DOCUMENT_DIRECTORY_NAME: str = "Documents"
USER_HOME_DIRECTORY_NAME: PosixPath = Path.home()

ABSOULTE_DOCUMENT_DIRECTORY_PATH: str = None

# used in app dirctory
SCRIPT_DIRECTORY_NAME = "APOD_NASA_SCRAPER"
TEMP_DIRECTORY_NAME = "temp"
IMAGE_STORAGE_DIRECTORY_NAME = "storage"


# File
DATABASE_NAME = "simple_database.json"

# DATABASE SCHEMA
simple_database_schema = {IMAGES: []}

#
website_url = "https://apod.nasa.gov/apod/"

working_document_path: PosixPath = None
working_document_temp_path: PosixPath = None
working_document_storage_path: PosixPath = None
working_database_path: PosixPath = None

working_database: dict = {}


# NETWORK LEVEL
def scrap_website(website_link) -> BeautifulSoup:
    logging.debug(f"Downalod website with link {website_link}")
    r = requests.get(website_link)

    if r.status_code != 200:
        raise Exception("Error in downloading website")

    return BeautifulSoup(r.content, "html.parser")


def download_image(image_absolute_link: str) -> requests.Response:
    logging.debug(f"Downalod image with link {image_absolute_link}")

    r = requests.get(image_absolute_link, stream=True)

    if r.status_code != 200:
        raise Exception("Error in downloading image")

    return r


def extract_image_link(website_html: BeautifulSoup) -> str:
    logging.debug("exctract image link ")

    images = website_html.find_all("img")

    image_link: str

    if images:
        image_link = images[0].attrs["src"]
    else:
        raise Exception("No image found")

    return image_link


def hash_text(link: str):
    logging.debug("Hashing text")

    link_byte = bytes(link, "utf-8")
    hash_object = hashlib.md5(link_byte)
    return str(hash_object.hexdigest())


def get_image_name(image_link) -> str:
    return image_link.split("/")[-1]


def get_image_absolute_link(website_url: str, image_link: str) -> str:
    if website_url.endswith("/"):
        return website_url + image_link
    else:
        return website_url + "/" + image_link


# LOCAL LEVEL
def validate_document_directory_path():
    logging.debug("validate Document path used in script")

    global working_document_path

    if ABSOULTE_DOCUMENT_DIRECTORY_PATH:
        document_path = Path(ABSOULTE_DOCUMENT_DIRECTORY_PATH)
    else:
        document_path = USER_HOME_DIRECTORY_NAME / USER_DOCUMENT_DIRECTORY_NAME

    if document_path.exists():
        working_document_path = document_path
    else:
        raise Exception(f"Document directory path does not exit {document_path}")


def check_script_directory():
    logging.debug("check if all directory exists")

    global working_document_storage_path
    global working_document_temp_path
    global working_database_path

    app_dir: PosixPath = working_document_path / SCRIPT_DIRECTORY_NAME

    if not app_dir.exists():
        logging.warning("App directory does not exist")
        logging.debug("Create app directory")
        create_directory(app_dir)

    working_document_temp_path = app_dir / TEMP_DIRECTORY_NAME
    if not working_document_temp_path.exists():
        logging.warning("Temp directory does not exist")
        create_directory(working_document_temp_path)

    working_document_storage_path = app_dir / IMAGE_STORAGE_DIRECTORY_NAME
    if not working_document_storage_path.exists():
        logging.warning("Storage directory does not exist")
        create_directory(working_document_storage_path)

    working_database_path = app_dir / DATABASE_NAME
    if not working_database_path.exists():
        logging.warning("database file does not exist")
        create_database(working_database_path)


def create_directory(directory_path: PosixPath):
    logging.debug(f"Create Directory  {directory_path}")
    directory_path.mkdir()


def create_database(database_path):
    logging.debug(f"Create database file  {database_path}")
    database_json = json.dumps(simple_database_schema)

    with open(str(database_path), "w") as f:
        f.write(database_json)


def load_database(database_path) -> dict:
    logging.debug(f"load database from  {database_path}")

    database_data = None
    with open(str(database_path), "r") as f:
        raw_data = f.read()
        # decoding
        database_data = json.loads(raw_data)

    return database_data


def write_database(database_path, database_data):
    logging.debug(f"Saving database to {database_path}")
    with open(database_path, "w") as f:
        json_data = json.dumps(database_data)
        f.write(json_data)


def check_if_image_already_exist(image_hash: str) -> bool:
    database_images = working_database[IMAGES]

    for image in database_images:
        if image["id"] == image_hash:
            return True

    return False


def save_image_to_file(image, save_path: str, file_name: str):

    image_path = working_document_storage_path / file_name

    with open(str(image_path), "wb") as f:
        f.write(image)


def save_image_data_to_database(image_hash, image_name, image_path):
    image_data = {
        "id": image_hash,
        "name": image_name,
        "path": str(image_path),
        "add-date": str(datetime.now()),
    }

    working_database[IMAGES].append(image_data)
    logging.debug(f"Update database add data {image_data}")


def save_image_in_temp_folder(image_bytes: bytes, image_name: str):
    image_path = working_document_temp_path / image_name

    with open(str(image_path), "wb") as f:
        shutil.copyfileobj(image_bytes, f)


def save_image_in_storage_folder(
    image_response: requests.Response, image_absolute_path: str
):
    logging.debug(f"Save image to storage directory {image_absolute_path}")
    with open(image_absolute_path, "wb") as f:
        image_response.raw.decode_content = True
        shutil.copyfileobj(image_response.raw, f)


def set_wallpaper(image_absolute_path):
    ctypes.windll.user32.SystemParametersInfoW(20, 0, image_absolute_path, 0)


def run_script():
    logging.debug("Run script")
    global working_database

    validate_document_directory_path()
    check_script_directory()

    absolute_database_path = str(working_database_path)

    working_database = load_database(absolute_database_path)

    website_html: BeautifulSoup = scrap_website(website_url)
    image_link: str = extract_image_link(website_html)

    image_name: str = get_image_name(image_link)
    # check if image already exist in database
    image_hash: str = hash_text(image_name)

    if check_if_image_already_exist(image_hash):
        logging.debug("image already exist in database")
        sys.exit(0)

    # if image does not exit
    image_absolute_link = get_image_absolute_link(website_url, image_link)
    image_response: requests.Response = download_image(image_absolute_link)

    # get image storage path
    image_absolute_storage_path: str = str(working_document_storage_path / image_name)
    # save image
    save_image_in_storage_folder(image_response, image_absolute_storage_path)
    # save data
    save_image_data_to_database(image_hash, image_name, image_absolute_storage_path)

    write_database(working_database_path, working_database)

    
    # set_wallpaper(image_absolute_storage_path)


if __name__ == "__main__":
    run_script()
