import os
import csv
import platform
import json


def clear_console():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


# Saves data to a json file. you can easily switch it to generate a text file or csv according to your needs.
def save(data, filename):
    os.makedirs("output", exist_ok=True)
    file_path = os.path.join("output", filename)

    try:
        with open(file_path, "w+") as jsonfile:
            json.dump(data, jsonfile)

        clear_console()
        print("File generated.")

    except Exception:
        clear_console()
        print("File not generated.")


def get_offices(filename):
    offices = set()
    with open(filename, "r") as file:
        doc = csv.reader(file)
        for row in doc:
            if row[2] != "OfficeName":
                offices.add((row[7], row[3]))

    output = list(sorted(offices))
    save(output, "offices.json")


def get_states(filename):
    states = set()
    with open(filename, "r") as file:
        doc = csv.reader(file)
        for row in doc:
            if row[8] != "StateName":
                states.add(row[8])

    output = list(sorted(states))
    save(output, "states.json")


def get_districts(filename):
    districts = set()
    with open(filename, "r") as file:
        doc = csv.reader(file)
        for row in doc:
            if row[7] != "District":
                districts.add((row[8], row[7]))
    output = list(sorted(districts))
    save(output, "districts.json")


def get_areas(filename):
    areas = set()
    with open(filename, "r") as file:
        doc = csv.reader(file)
        for row in doc:
            if row[4] != "Pincode":
                areas.add((row[3], row[4], row[5], row[6]))
    output = list(sorted(areas))
    save(output, "areas.json")
