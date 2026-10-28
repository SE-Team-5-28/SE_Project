# Hostel Management System

## Project Overview

The Hostel Management System is a web-based system designed to manage student hostel records, hostel and room information, room allocation, occupancy, room transfer requests, complaints, and administrative reporting.

The system is intended to provide role-based access for different users, including students, wardens, hostel administrators, and system administrators.

## Team Members

| Name           | SRN           |
| -------------- | ------------- |
| R Agilesh      | PES2UG24CS385 |
| R G Nithik     | PES2UG24CS386 |
| R Muralidharan | PES2UG24CS387 |
| R Pooja        | PES2UG24CS388 |

## Key Features

* User authentication and role-based access control
* Student profile and hostel record management
* Hostel, block, and room management
* Room allocation and occupancy management
* Student check-in and check-out
* Room transfer requests and approval/rejection
* Complaint registration and status tracking
* Occupancy and vacancy reports
* Pending transfer and unresolved complaint reports
* Audit logging
* Search and retrieval of hostel information

## User Roles

The system defines the following user classes:

* Student – Accesses relevant hostel information and submits requests/complaints.
* Warden – Manages hostel-related operations and student requests.
* Hostel Administrator – Handles hostel, room, allocation, and reporting operations.
* System Administrator – Manages system-level administration and access.

## Prerequisites
- Python 3
- MySQL Server
- Git

## Setup
1. Clone the repository.
2. Create and activate a Python virtual environment.
3. Install dependencies using `pip install -r requirements.txt`.
4. Create the MySQL database `hms_db`.
5. Copy `.env.example` to `.env`.
6. Configure your local database credentials and Django secret key.
7. Run database migrations using `python manage.py migrate`.
8. Start the development server using `python manage.py runserver`.

## Environment Configuration
See `.env.example` for the required environment variable names.
Never commit `.env` or real credentials to Git.

## Database
The project uses MySQL through Django's MySQL database backend.

The SRS defines the system scope, functional requirements, non-functional requirements, security requirements, user roles, interfaces, constraints, assumptions, and requirements traceability.

The Software Test Plan defines the planned test levels, test types, test cases, test environment, testing responsibilities, test metrics, and requirements-to-test-case traceability.

## Technology

The following is the proposed technology environment:

* Frontend: Web-based user interface
* Backend: Python Django/Flask or PHP Laravel
* Database: Relational database such as MySQL
* Communication: HTTPS/TLS
* Deployment: Networked server environment

The final implementation technology will be reflected here as development progresses.

## Testing

The project test plan covers:

* Unit Testing
* Integration Testing
* System Testing
* User Acceptance Testing
* Functional Testing
* Regression Testing
* Performance Testing
* Reliability Testing
* Data Integrity Testing
* Usability Testing
* Recovery Testing
* Security Testing

Test cases are mapped to the functional, non-functional, and security requirements defined in the SRS.

## Project Status

Current Phase: Requirements and Test Planning

### Completed Documentation

* Software Requirements Specification
* Software Test Plan

### Planned

* System architecture and design
* Implementation
* Unit and integration testing
* System validation
* CI/CD pipeline
* Security validation
* Final project documentation

## Repository Structure

```text
Hostel-Management-System/
│
├── README.md
│
└── docs/
    ├── SRS.pdf
    └── Test_Plan.pdf
```

## Project Scope

The system focuses on hostel record management, room management, room allocation, occupancy, transfers, complaints, and administrative reporting.

University-wide academic administration and payment processing beyond potential future API integration are outside the current project scope.
