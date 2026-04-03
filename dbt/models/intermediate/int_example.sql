{{ config(materialized='table') }}

-- depends_on: {{ ref('stg_example') }}

SELECT *
FROM {{ ref('stg_example') }}
