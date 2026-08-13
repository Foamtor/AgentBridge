-- Model aliases are user-facing labels. Keep them readable while preventing
-- values that cannot be addressed safely through the admin URL routes.
ALTER TABLE bridge_model_configs
    DROP CONSTRAINT IF EXISTS bridge_model_configs_alias_format;

ALTER TABLE bridge_model_configs
    ADD CONSTRAINT bridge_model_configs_alias_format
    CHECK (
        length(alias) BETWEEN 1 AND 64
        AND btrim(alias) = alias
        AND alias !~ '[[:cntrl:]]'
        AND strpos(alias, '/') = 0
        AND strpos(alias, chr(92)) = 0
        AND strpos(alias, '?') = 0
        AND strpos(alias, '#') = 0
    );
