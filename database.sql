-- Drop database if exists
DROP DATABASE IF EXISTS wearcare;

-- Create database
CREATE DATABASE wearcare;
USE wearcare;

-- Users table
CREATE TABLE users(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Donations table
CREATE TABLE donations(
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    user_name VARCHAR(100) NOT NULL,
    cloth_type VARCHAR(50) NOT NULL,
    size VARCHAR(20) NOT NULL,
    condition_status VARCHAR(50) NOT NULL,
    address TEXT NOT NULL,
    image VARCHAR(200),
    status VARCHAR(50) DEFAULT 'Pending',
    is_free TINYINT(1) NOT NULL DEFAULT 1,
    price DECIMAL(10,2) NULL,
    phone VARCHAR(30) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Notifications table (for approval/rejection updates)
CREATE TABLE notifications(
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP NULL
);

-- Purchase requests (buyer -> donor approval)
CREATE TABLE purchase_requests(
    id INT AUTO_INCREMENT PRIMARY KEY,
    donation_id INT NOT NULL,
    buyer_user_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create a test user (password: password123)
INSERT INTO users (name, email, password) VALUES 
('Test User', 'test@example.com', 'scrypt:32768:8:1$d8yB2qW5xK7mR3tL$c1a2b3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z2a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4a5b6c7d8e9f0');

-- Create admin user (password: admin123)
INSERT INTO users (name, email, password) VALUES 
('Admin User', 'admin@wearcare.com', 'scrypt:32768:8:1$y9L4mN7pQ2rS5tU$e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z2a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4a5b6c7d8e9f0');

-- Sample donation
INSERT INTO donations (user_name, cloth_type, size, condition_status, address, image, status) VALUES
('Test User', 'T-Shirt', 'L', 'Good', '123 Main St, City, State 12345', '', 'Pending');

-- Verify data
SELECT * FROM users;
SELECT * FROM donations;