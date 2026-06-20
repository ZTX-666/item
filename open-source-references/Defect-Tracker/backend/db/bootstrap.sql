CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO roles (id, name) VALUES
    (gen_random_uuid(), 'quality_auditor'),
    (gen_random_uuid(), 'quality_repair'),
    (gen_random_uuid(), 'quality_rep'),
    (gen_random_uuid(), 'quality_tech'),
    (gen_random_uuid(), 'quality_engineer'),
    (gen_random_uuid(), 'safety_rep'),
    (gen_random_uuid(), 'safety_tech'),
    (gen_random_uuid(), 'safety_engineer'),
    (gen_random_uuid(), 'team_lead'),
    (gen_random_uuid(), 'production_lead'),
    (gen_random_uuid(), 'team_manager'),
    (gen_random_uuid(), 'manufacturing_engineer'),
    (gen_random_uuid(), 'business_lead')
ON CONFLICT DO NOTHING;

INSERT INTO scopes (id, name) VALUES
    (gen_random_uuid(), 'quality:defects:read'),
    (gen_random_uuid(), 'quality:defects:write'),
    (gen_random_uuid(), 'quality:dispo:write'),
    (gen_random_uuid(), 'quality:reports:read'),
    (gen_random_uuid(), 'quality:reports:write'),
    (gen_random_uuid(), 'quality:reports:approve'),
    (gen_random_uuid(), 'safety:incidents:read'),
    (gen_random_uuid(), 'safety:incidents:write'),
    (gen_random_uuid(), 'safety:incidents:approve'),
    (gen_random_uuid(), 'production:attendance:read'),
    (gen_random_uuid(), 'production:attendance:write'),
    (gen_random_uuid(), 'production:attendance:approve'),
    (gen_random_uuid(), 'production:performance:read'),
    (gen_random_uuid(), 'production:performance:write'),
    (gen_random_uuid(), 'production:performance:approve')
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('quality:defects:read', 'quality:defects:write')
WHERE r.name = 'quality_auditor'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('quality:defects:read', 'quality:defects:write', 'quality:dispo:write')
WHERE r.name = 'quality_repair'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('quality:defects:read', 'quality:defects:write', 'quality:dispo:write', 'quality:reports:read', 'quality:reports:write')
WHERE r.name = 'quality_rep'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('quality:defects:read', 'quality:defects:write', 'quality:dispo:write', 'quality:reports:read', 'quality:reports:write', 'quality:reports:approve')
WHERE r.name = 'quality_tech'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('quality:defects:read', 'quality:defects:write', 'quality:dispo:write', 'quality:reports:read', 'quality:reports:write', 'quality:reports:approve')
WHERE r.name = 'quality_engineer'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('safety:incidents:read', 'safety:incidents:write')
WHERE r.name = 'safety_rep'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('safety:incidents:read', 'safety:incidents:write', 'safety:incidents:approve')
WHERE r.name = 'safety_tech'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('safety:incidents:read', 'safety:incidents:write', 'safety:incidents:approve')
WHERE r.name = 'safety_engineer'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('production:attendance:read', 'production:attendance:write', 'production:performance:read', 'production:performance:write')
WHERE r.name = 'team_lead'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('production:performance:read', 'production:performance:write')
WHERE r.name = 'production_lead'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('production:attendance:read', 'production:attendance:write', 'production:attendance:approve', 'production:performance:read', 'production:performance:write', 'production:performance:approve', 'quality:defects:read', 'quality:reports:read', 'safety:incidents:read')
WHERE r.name = 'team_manager'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('production:attendance:read', 'production:attendance:write', 'production:attendance:approve', 'production:performance:read', 'production:performance:write', 'production:performance:approve')
WHERE r.name = 'manufacturing_engineer'
ON CONFLICT DO NOTHING;

INSERT INTO role_scopes (id, role_id, scope_id)
SELECT gen_random_uuid(), r.id, s.id
FROM roles r
JOIN scopes s ON s.name IN ('production:attendance:read', 'production:attendance:write', 'production:attendance:approve', 'production:performance:read', 'production:performance:write', 'production:performance:approve', 'quality:defects:read', 'quality:reports:read', 'safety:incidents:read')
WHERE r.name = 'business_lead'
ON CONFLICT DO NOTHING;

INSERT INTO users (id, username, email, password_hash) VALUES
    (gen_random_uuid(), 'qauditor', 'qauditor@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'qrepair', 'qrepair@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'qrep', 'qrep@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'qtech', 'qtech@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'qengineer', 'qengineer@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'srep', 'srep@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'stech', 'stech@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'sengineer', 'sengineer@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'tlead', 'tlead@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'plead', 'plead@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'tmanager', 'tmanager@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'mengineer', 'mengineer@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO'),
    (gen_random_uuid(), 'blead', 'blead@demo.com', '$2b$12$UdSG4u86fUaF5ty4uKNwYeQwsFGlY0JM/LZJPqgDoO1Mxg8Z4xyZO')
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'quality_auditor'
WHERE u.email = 'qauditor@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'quality_repair'
WHERE u.email = 'qrepair@demo.com'  
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'quality_rep'
WHERE u.email = 'qrep@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'quality_tech'
WHERE u.email = 'qtech@demo.com'
ON CONFLICT DO NOTHING; 

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'quality_engineer'
WHERE u.email = 'qengineer@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'safety_rep'
WHERE u.email = 'srep@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'safety_tech'
WHERE u.email = 'stech@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'safety_engineer'
WHERE u.email = 'sengineer@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id    
FROM users u
JOIN roles r ON r.name = 'team_lead'
WHERE u.email = 'tlead@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'production_lead'
WHERE u.email = 'plead@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'team_manager'
WHERE u.email = 'tmanager@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'manufacturing_engineer'
WHERE u.email = 'mengineer@demo.com'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (id, user_id, role_id)
SELECT gen_random_uuid(), u.id, r.id
FROM users u
JOIN roles r ON r.name = 'business_lead'
WHERE u.email = 'blead@demo.com'
ON CONFLICT DO NOTHING;

