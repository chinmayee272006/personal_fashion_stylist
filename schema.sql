-- ============================================================
-- Personal Fashion Stylist — Database Schema
-- Database : fashion_db
-- Engine   : InnoDB (for FK support)
-- ============================================================

CREATE DATABASE IF NOT EXISTS fashion_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE fashion_db;

-- ----------------------------------------------------------
-- 1. USERS  –  authentication & account info
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 2. PROFILES  –  body measurements & style preferences
--    One-to-one with users
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS profiles (
    profile_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL UNIQUE,
    full_name     VARCHAR(100),
    age           INT,
    gender        ENUM('Male', 'Female', 'Non-Binary', 'Other'),
    height_cm     DECIMAL(5,1),
    weight_kg     DECIMAL(5,1),
    body_type     VARCHAR(50),
    skin_tone     VARCHAR(50),
    favourite_colour VARCHAR(50),
    style_pref    VARCHAR(255)  COMMENT 'e.g. Casual, Formal, Ethnic, Streetwear',
    occasion      VARCHAR(255)  COMMENT 'e.g. Casual, Formal, Party',
    profile_pic   VARCHAR(255)  COMMENT 'path or URL to uploaded photo',
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_profiles_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 3. OUTFITS  –  catalog of outfit items / combinations
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS outfits (
    outfit_id     INT AUTO_INCREMENT PRIMARY KEY,
    outfit_name   VARCHAR(150) NOT NULL,
    category      VARCHAR(50)   COMMENT 'e.g. Casual, Formal, Party, Ethnic',
    season        VARCHAR(30)   COMMENT 'e.g. Summer, Winter, All-Season',
    gender_target ENUM('Male', 'Female', 'Unisex'),
    suitable_body_types VARCHAR(255) COMMENT 'CSV of body types this outfit suits',
    suitable_skin_tones VARCHAR(255) COMMENT 'CSV of skin tones this complements',
    colour        VARCHAR(50)   COMMENT 'Primary colour of the outfit',
    image_url     VARCHAR(255),
    description   TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 4. RECOMMENDATIONS  –  AI-generated suggestions per user
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS recommendations (
    rec_id        INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    outfit_id     INT NOT NULL,
    score         DECIMAL(4,2)  COMMENT 'confidence / relevance score 0-10',
    reason        TEXT          COMMENT 'why this was recommended',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_rec_user
        FOREIGN KEY (user_id)   REFERENCES users(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_rec_outfit
        FOREIGN KEY (outfit_id) REFERENCES outfits(outfit_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 5. FAVOURITES  –  outfits saved / liked by users
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS favourites (
    fav_id        INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    outfit_id     INT NOT NULL,
    saved_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_user_outfit (user_id, outfit_id),

    CONSTRAINT fk_fav_user
        FOREIGN KEY (user_id)   REFERENCES users(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_fav_outfit
        FOREIGN KEY (outfit_id) REFERENCES outfits(outfit_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 6. FEEDBACK  –  user ratings / comments on recommendations
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id   INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    outfit_id     INT            COMMENT 'direct outfit reference for feedback',
    rec_id        INT  DEFAULT NULL  COMMENT 'optional link to a recommendation',
    rating        TINYINT       CHECK (rating BETWEEN 1 AND 5),
    comment       TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_fb_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_fb_rec
        FOREIGN KEY (rec_id)  REFERENCES recommendations(rec_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 7. ADMINS  –  separate admin authentication
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS admins (
    admin_id      INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
