SELECT
    id AS user_id,
    account_id
FROM {{ source('raw', 'app_users') }}
