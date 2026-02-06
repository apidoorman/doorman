# API Builder Verification Steps

## 1. Access the Page
- Navigate to the "APIs" page
- Click on the "API Builder" button
- Verify you are redirected to `/api-builder`

## 2. Form Validation
- Try to submit the empty form
- Verify validation error for "API Name", "Version", "Resource Name"

## 3. Create a CRUD API
- Fill in the form:
  - API Name: `test-crud-api`
  - Version: `v1`
  - Resource Name: `products`
  - Active: Checked
- Click "Build API"

## 4. Verify API Creation
- Check if redirected to API list or details page
- Find `test-crud-api` in the list
- Verify badges: `REST`

## 5. Verify Endpoints
- Click "View Endpoints" for the new API
- Verify 5 endpoints exist:
  - `GET /products`
  - `POST /products`
  - `GET /products/{id}`
  - `PUT /products/{id}`
  - `DELETE /products/{id}`

## 6. Functional Test
- Use the API via curl or Postman:
  - POST to `/api/rest/test-crud-api/v1/products`
  - GET from `/api/rest/test-crud-api/v1/products`
