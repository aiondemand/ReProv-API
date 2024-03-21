
# Provenance-API

This repository is an API-based solution enabling users to register and execute workflows seamlessly by integrating with the [REANA](https://reanahub.io/) execution system. It also offers the capability to capture and visualize data provenance of the workflow executions, based on the [W3C-PROV](https://www.w3.org/TR/prov-o/) standard.

The project consists of three key components:
 - [FastAPI](https://fastapi.tiangolo.com/): Core component enabling RESTful API interactions with the platform.
- [Keycloak](https://www.keycloak.org/): Authentication and access control system ensuring secure user authentication and user grouping
- [MySQL Database](https://www.mysql.com/): Database system serving as the backend for efficient data storage and retrieval.

All three components are deployed in a **dockerized** environment in order to ensure *scalability*, *portability*, and *ease of management*.



## Key Features

 - User authentication using keycloak
 - Registration of a workflow ([CWL](https://www.commonwl.org/) workflows are currently supported).
 - Integrate with REANA system to execute previously registered workflows.
 - [CRUD](https://www.codecademy.com/article/what-is-crud) operations both for registered and executed workflows.
 - Capture data provenance for previously executed workflow.
 -  Visualize data provenance by generating graph-based PNG representations, allowing for clear and intuitive 
exploration of workflow dependencies and data flow.


## Prerequisites
- `Linux / macOS`
- `Python version >= 3.10 (preferably 3.10)`
- `docker version >= 24.0.7`
- `docker-compose version >= 1.29.2`
-  Access to an installed *REANA* instance. You will need *URL* of the service along with the corresponding *ACCESS TOKEN* . If you are collaborating with *[ID-IS](https://www.iit.demokritos.gr/labs/idis/)* group, feel free to contact ant.ganios@iit.demokritos.gr for more details on this.

## Local Installation
In order to install the platform locally, follow the steps outlined below 

#### Clone the repository
	
    git clone https://github.com/id-is/provenance-api

#### Move into the local directory and create the new virtual environment

    cd provenance-api
    python -m venv venv
    source venv/bin/activate

#### Install dependencies (this may take a few minutes)

    pip install -r requirements.txt

#### Create a *.env* file

    touch .env

#### Add values to the `.env` file
The values you add to the `.env` file are the ones that should be defined in order to run the application. Each value should follow the format `KEY=VALUE`, where `KEY` is the name of the environment variable and `VALUE` is its corresponding value.

Using your favorite editor, you have to adjust the following variables based on your system. 
Some things to consider are:
 1. Every environmental variable with the *MYSQL* prefix (**except MYSQL_SERVER**) can be configured as desired.
 2. Every environmental variable with the *KEYCLOAK* prefix (**except KEYCLOAK_ADMIN_USERNAME and KEYCLOAK_ADMIN_PASSWORD) must not be changed**

Note that `KEYCLOAK_CLIENT_SECRET` must have empty value as demonstrated below

    REANA_SERVER_URL=<URL OF REANA INSTANCE>
    REANA_ACCESS_TOKEN=<TOKEN OF REANA INSTANCE>
    
    MYSQL_SERVER=prov-db
    MYSQL_ROOT_PASSWORD=root_password
    MYSQL_DATABASE=prov_db
    MYSQL_USER=user
    MYSQL_PASSWORD=password
    
    KEYCLOAK_SERVER_URL=http://prov-keycloak:8080/
    KEYCLOAK_REALM=prov
    KEYCLOAK_AUTHORIZATION_URL=http://localhost:8080/realms/prov/protocol/openid-connect/auth
    KEYCLOAK_TOKEN_URL=http://localhost:8080/realms/prov/protocol/openid-connect/token
    KEYCLOAK_CLIENT_ID=api
    KEYCLOAK_CLIENT_SECRET=
    KEYCLOAK_ADMIN_USERNAME=admin
    KEYCLOAK_ADMIN_PASSWORD=admin


Create and start all 3 containers using *docker-compose*.

    docker compose up -d


Once started, you should be able to

 1.  Visit the REST API at http://localhost:8000/docs 
Instructions for using the API will be provided in the next sections
 3. Visit Keycloak at http://localhost:8080/ . In the current configuration Keylcoak is filled with 5 users and 2 groups. Each user has credentials of the form *user_i / password_i* where i $\in [1,\dots,5]$.
 You can have admin access by using the credentials defined above. 


## Usage

#### Authenticate
Fisrt thing that you have to do is authenticate from the API  against Keycloak service. 
You'll find the authentication button located at the top right of the screen.

![screenshot](https://github.com/id-is/provenance-api/blob/10-add-readme-file/media/authorize_button.png)

After you click on it, the authentication prompt will be opened. You have to add *api* to *client_id* field as it is demonstrated next.

![screenshot](https://github.com/id-is/provenance-api/blob/10-add-readme-file/media/authorize_prompt.png)


Next, click authorize button and you will be redirected to keycloak to fill your credentials. In this example, we are using *user_1* for user and *password_1* for password.

![screenshot](https://github.com/id-is/provenance-api/blob/10-add-readme-file/media/keycloak_prompt.png)


Finally, if the credentials are correct, you are done with the authentication process and the following screen must appear.

![screenshot](https://github.com/id-is/provenance-api/blob/10-add-readme-file/media/authorize_response.png)

