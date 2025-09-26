# Mercedes W222 OBD Scanner - API Documentation

**Version:** 3.0.0
**Last Updated:** 2025-09-27

## 1. Introduction

This document provides detailed documentation for the **Mercedes W222 OBD Scanner** API. The API is built with FastAPI and provides endpoints for user management, authentication, OBD data, payments, and more.

## 2. Authentication

All API endpoints require a valid JWT token to be passed in the `Authorization` header as a Bearer token.

`Authorization: Bearer <your_jwt_token>`

### 2.1. Get Token

- **Endpoint:** `/api/auth/token`
- **Method:** `POST`
- **Description:** Authenticate a user and get a JWT token.
- **Request Body:**
  ```json
  {
    "username": "your_username",
    "password": "your_password"
  }
  ```
- **Response:**
  ```json
  {
    "access_token": "your_jwt_token",
    "token_type": "bearer"
  }
  ```

## 3. Users

### 3.1. Create User

- **Endpoint:** `/api/users`
- **Method:** `POST`
- **Description:** Create a new user.
- **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "your_password",
    "first_name": "John",
    "last_name": "Doe"
  }
  ```

### 3.2. Get User

- **Endpoint:** `/api/users/me`
- **Method:** `GET`
- **Description:** Get the current user's details.

## 4. OBD Data

### 4.1. Get Real-time Data

- **Endpoint:** `/ws/obd`
- **Protocol:** WebSocket
- **Description:** Stream real-time OBD data.

### 4.2. Get Trip History

- **Endpoint:** `/api/trips`
- **Method:** `GET`
- **Description:** Get a list of past trips.

## 5. Payments

### 5.1. Get Plans

- **Endpoint:** `/api/payments/plans`
- **Method:** `GET`
- **Description:** Get a list of available subscription plans.

### 5.2. Create Subscription

- **Endpoint:** `/api/payments/subscriptions`
- **Method:** `POST`
- **Description:** Create a new subscription.
- **Request Body:**
  ```json
  {
    "plan_id": "professional",
    "payment_method_id": "pm_card_visa"
  }
  ```

## 6. Webhooks

### 6.1. Stripe Webhook

- **Endpoint:** `/api/payments/webhooks/stripe`
- **Method:** `POST`
- **Description:** Handle Stripe webhook events.

## 7. Error Handling

The API uses standard HTTP status codes to indicate the success or failure of a request.

- `200 OK`: The request was successful.
- `201 Created`: The resource was created successfully.
- `400 Bad Request`: The request was invalid.
- `401 Unauthorized`: Authentication failed.
- `403 Forbidden`: The user is not authorized to perform the action.
- `404 Not Found`: The resource was not found.
- `500 Internal Server Error`: An unexpected error occurred.

