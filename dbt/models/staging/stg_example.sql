{{ config(
    materialized='incremental',
    unique_key='segment_id'
) }}

SELECT *
FROM {{ ref('dim_example') }}
