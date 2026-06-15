## Preliminary

You need [pipenv](https://pipenv.pypa.io/en/latest/) to run the project. For the recommended installation, please run the following command on your machine:
```
pip install --user pipenv
```

If you are using Windows as OS, you should use the PowerShell to install pipenv and
run the project.

You don't necessarily need the Docker container of the lecture.

## Installation

Install the project using pipenv in the directory where the `Pipfile` resides. The command
```
pipenv install
```
will create a virtual environment and install the required dependencies. Note that we use
Python3.12, you may also specify the applied Python installation explicitly using
```
pipenv --python /path/to/python3.12 install
```

When using an IDE like PyCharm you want to make sure that that virtual environment is used for the project.

Then
```
pipenv shell
```
will activate that virtual environment.

After working on the project, the virtual environment can be deactivated again using the
```
exit
```
command.

## Unit Tests

To run the unit tests in the virtual environment, use the following command:

```
python manage.py test
```

Recall to disable the failing tests and enable them one by one to see the failing tests. 
Note that the tests use the fixture `database_dump.json`.

## Server

To run the server in the virtual environment, use the following command:
```
python manage.py runserver
```

You can access the server in a browser of your choice under http://127.0.0.1:8000/. To stop the server again press `Ctrl-C`.

## Models, Database, and Fake Data

Use the script
```
recreate_models_and_data.sh
```
to recreate the migrations, database, fake data and fixtures.
