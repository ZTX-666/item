INSERT INTO defects (
    id, created_at, reported_by, category, subcategory,
    description, absn, assigned_to, status
) VALUES
('11111111-1111-1111-1111-111111111111', '2024-01-01T08:00:00Z', 'auditor_1', 'damaged', 'scratch', 'Minor scratch on housing', '3471', 'operator_3', 'repaired'),
('22222222-2222-2222-2222-222222222222', '2024-01-01T09:15:00Z', 'auditor_2', 'wrong', 'wrong_part', 'Incorrect bolt installed', '0000', NULL, 'open'),
('33333333-3333-3333-3333-333333333333', '2024-01-02T10:30:00Z', 'auditor_1', 'damaged', 'dent', 'Dent on longblock cover', '3471', 'operator_3', 'repaired'),
('44444444-4444-4444-4444-444444444444', '2024-01-02T11:00:00Z', 'auditor_3', 'wrong', 'wrong_orientation', 'Bracket installed backwards', '3452', NULL, 'open'),
('55555555-5555-5555-5555-555555555555', '2024-01-03T07:45:00Z', 'auditor_2', 'damaged', 'crack', 'Hairline crack detected', '3471', 'operator_4', 'repaired'),
('66666666-6666-6666-6666-666666666666', '2024-01-03T08:20:00Z', 'auditor_1', 'wrong', 'missing_component', 'Missing gasket', '0000', NULL, 'open'),
('77777777-7777-7777-7777-777777777777', '2024-01-04T09:00:00Z', 'auditor_4', 'damaged', 'scratch', 'Surface scratch near fitting', '3471', NULL, 'open'),
('88888888-8888-8888-8888-888888888888', '2024-01-04T10:15:00Z', 'auditor_2', 'wrong', 'wrong_part', 'Incorrect valve type', '3452', 'operator_5', 'repaired'),
('99999999-9999-9999-9999-999999999999', '2024-01-05T08:30:00Z', 'auditor_1', 'damaged', 'dent', 'Small dent on bracket', '3471', NULL, 'open'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2024-01-05T09:10:00Z', 'auditor_3', 'wrong', 'wrong_part', 'Wrong fastener used', '0000', NULL, 'open'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '2024-01-06T07:55:00Z', 'auditor_4', 'damaged', 'crack', 'Crack near mounting point', '3452', 'operator_6', 'repaired'),
('cccccccc-cccc-cccc-cccc-cccccccccccc', '2024-01-06T08:40:00Z', 'auditor_2', 'damaged', 'scratch', 'Scratch on painted surface', '3471', NULL, 'open');

