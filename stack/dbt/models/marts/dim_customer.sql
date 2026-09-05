SELECT
    a.customer_id,
    a.name,
    COUNT(u.user_id) AS user_count
FROM {{ ref('stg_accounts') }} a
LEFT JOIN {{ ref('stg_users') }} u ON u.account_id = a.customer_id
GROUP BY 1, 2
