SELECT
    id AS customer_id,
    name
FROM {{ source('raw', 'salesforce_account') }}
