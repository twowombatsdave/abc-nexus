{{ config(materialized='table') }}

-- depends_on: {{ ref('int_example') }}

SELECT *
FROM {{ ref('int_example') }}
