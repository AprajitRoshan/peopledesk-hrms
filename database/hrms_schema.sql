CREATE DATABASE IF NOT EXISTS hrms_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hrms_db;

CREATE TABLE IF NOT EXISTS users (
  id INT NOT NULL AUTO_INCREMENT,
  full_name VARCHAR(150) NOT NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'employee',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id), UNIQUE KEY uq_users_email (email), KEY ix_users_id (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS employees (
  id INT NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  employee_code VARCHAR(20) NOT NULL,
  department VARCHAR(100) NOT NULL,
  designation VARCHAR(100) NOT NULL,
  phone VARCHAR(20) NULL,
  monthly_salary DECIMAL(12,2) NOT NULL DEFAULT 0,
  joining_date DATE NOT NULL,
  employment_status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id), UNIQUE KEY uq_employees_user_id (user_id), UNIQUE KEY uq_employees_code (employee_code),
  KEY ix_employees_id (id), KEY ix_employees_employee_code (employee_code),
  CONSTRAINT fk_employees_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS attendance (
  id INT NOT NULL AUTO_INCREMENT,
  employee_id INT NOT NULL,
  work_date DATE NOT NULL,
  check_in DATETIME NULL,
  check_out DATETIME NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'present',
  correction_note VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id), KEY ix_attendance_id (id), KEY ix_attendance_employee_id (employee_id), KEY ix_attendance_work_date (work_date),
  UNIQUE KEY uq_attendance_employee_day (employee_id, work_date),
  CONSTRAINT fk_attendance_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS leave_requests (
  id INT NOT NULL AUTO_INCREMENT,
  employee_id INT NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  leave_type VARCHAR(40) NOT NULL DEFAULT 'annual',
  reason TEXT NOT NULL,
  review_note TEXT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  reviewed_by INT NULL,
  reviewed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id), KEY ix_leaves_employee_id (employee_id), KEY ix_leaves_status (status),
  CONSTRAINT fk_leaves_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
  CONSTRAINT fk_leaves_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
  id INT NOT NULL AUTO_INCREMENT,
  actor_user_id INT NULL,
  action VARCHAR(80) NOT NULL,
  entity_type VARCHAR(80) NOT NULL,
  entity_id VARCHAR(80) NULL,
  details TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id), KEY ix_audit_actor (actor_user_id), KEY ix_audit_action (action), KEY ix_audit_created (created_at),
  CONSTRAINT fk_audit_actor FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Day 2: payroll records and notification delivery log.
CREATE TABLE IF NOT EXISTS payroll_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    pay_period VARCHAR(7) NOT NULL,
    base_salary DECIMAL(12,2) NOT NULL,
    allowances DECIMAL(12,2) NOT NULL DEFAULT 0,
    deductions DECIMAL(12,2) NOT NULL DEFAULT 0,
    adjustment_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    adjustment_note VARCHAR(500) NULL,
    attendance_days INT NOT NULL DEFAULT 0,
    paid_leave_days INT NOT NULL DEFAULT 0,
    lop_days INT NOT NULL DEFAULT 0,
    lop_deduction DECIMAL(12,2) NOT NULL DEFAULT 0,
    net_salary DECIMAL(12,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'processed',
    locked_at DATETIME NULL,
    credited_at DATETIME NULL,
    processed_by INT NULL,
    processed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_payroll_employee_period UNIQUE (employee_id, pay_period),
    CONSTRAINT fk_payroll_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    CONSTRAINT fk_payroll_processor FOREIGN KEY (processed_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_payroll_period (pay_period),
    INDEX ix_payroll_employee (employee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notification_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recipient VARCHAR(255) NOT NULL,
    template_key VARCHAR(80) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'logged',
    error_message TEXT NULL,
    related_entity_type VARCHAR(80) NULL,
    related_entity_id VARCHAR(80) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_notification_recipient (recipient),
    INDEX ix_notification_template (template_key),
    INDEX ix_notification_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Day 3: leave balances and secure employee document metadata. File contents
-- are stored in backend/storage/employee_documents, not in the database.
CREATE TABLE IF NOT EXISTS leave_balances (
  id INT NOT NULL AUTO_INCREMENT, employee_id INT NOT NULL, leave_type VARCHAR(40) NOT NULL,
  allocated_days INT NOT NULL DEFAULT 0, used_days INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id), UNIQUE KEY uq_leave_balance_employee_type (employee_id, leave_type),
  KEY ix_leave_balances_employee (employee_id),
  CONSTRAINT fk_leave_balances_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS employee_documents (
  id INT NOT NULL AUTO_INCREMENT, employee_id INT NOT NULL, original_filename VARCHAR(255) NOT NULL,
  storage_key VARCHAR(80) NOT NULL, content_type VARCHAR(100) NOT NULL, file_size INT NOT NULL,
  uploaded_by INT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id), UNIQUE KEY uq_employee_documents_storage_key (storage_key), KEY ix_employee_documents_employee (employee_id),
  CONSTRAINT fk_employee_documents_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
  CONSTRAINT fk_employee_documents_uploader FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
