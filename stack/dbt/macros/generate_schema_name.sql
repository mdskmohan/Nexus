{#
  Use the custom schema verbatim rather than dbt's default of appending it to the
  target schema. Without this, `+schema: marts` lands models in `public_marts`,
  which makes warehouse schema names depend on whose target they were built with.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
