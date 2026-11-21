-- PlaceIQ database schema (MySQL 5.7+ / 8.x, MariaDB 10.3+)
-- Option A (recommended): python database/init_db.py
-- Option B (manual):      mysql -u root -p < database/schema.sql
--                         then run: python database/init_db.py   (creates officer + departments)

CREATE DATABASE IF NOT EXISTS placeiq CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE placeiq;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(160) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('student','officer') NOT NULL,
  designation VARCHAR(120) NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS departments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(60) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS students (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  usn VARCHAR(20) NOT NULL UNIQUE,
  dept VARCHAR(60) NOT NULL,
  semester TINYINT NOT NULL DEFAULT 1,
  grad_year SMALLINT NULL,
  year_of_study TINYINT NULL,
  cgpa DECIMAL(4,2) NOT NULL DEFAULT 0,
  backlogs TINYINT NOT NULL DEFAULT 0,
  tenth_pct DECIMAL(5,2) NULL,
  twelfth_pct DECIMAL(5,2) NULL,
  phone VARCHAR(20) NULL,
  skills TEXT NULL,
  languages TEXT NULL,
  certifications TEXT NULL,
  projects TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS resumes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  stored_name VARCHAR(80) NOT NULL,
  size_bytes INT NOT NULL,
  text_content MEDIUMTEXT NULL,
  score TINYINT NULL,
  analysis_json MEDIUMTEXT NULL,
  review_status ENUM('Pending','Approved','Changes requested') NOT NULL DEFAULT 'Pending',
  review_note VARCHAR(500) NULL,
  uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_resumes_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  INDEX idx_resumes_student (student_id, uploaded_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS companies (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  industry VARCHAR(80) NULL,
  website VARCHAR(160) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS jobs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  company_id INT NOT NULL,
  role VARCHAR(120) NOT NULL,
  description TEXT NULL,
  package_lpa DECIMAL(5,2) NOT NULL DEFAULT 0,
  min_cgpa DECIMAL(4,2) NOT NULL DEFAULT 0,
  max_backlogs TINYINT NOT NULL DEFAULT 0,
  allowed_depts VARCHAR(255) NULL,
  skills TEXT NULL,
  deadline DATE NOT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_jobs_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS applications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  job_id INT NOT NULL,
  student_id INT NOT NULL,
  status ENUM('Applied','Under Review','Shortlisted','Technical Interview','HR Interview','Selected','Rejected')
         NOT NULL DEFAULT 'Applied',
  applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_application (job_id, student_id),
  CONSTRAINT fk_app_job FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_app_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS interviews (
  id INT AUTO_INCREMENT PRIMARY KEY,
  application_id INT NOT NULL,
  round_name ENUM('Aptitude Round','Technical Round','HR Round') NOT NULL,
  scheduled_date DATE NOT NULL,
  scheduled_time TIME NULL,
  venue VARCHAR(160) NULL,
  notes VARCHAR(300) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_interview_round (application_id, round_name),
  CONSTRAINT fk_int_app FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS placement_results (
  id INT AUTO_INCREMENT PRIMARY KEY,
  application_id INT NOT NULL UNIQUE,
  package_lpa DECIMAL(5,2) NOT NULL,
  declared_on DATE NOT NULL,
  CONSTRAINT fk_res_app FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notifications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  message VARCHAR(300) NOT NULL,
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_notif_user (user_id, is_read, created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS settings (
  k VARCHAR(60) PRIMARY KEY,
  v VARCHAR(255) NOT NULL
) ENGINE=InnoDB;
