CREATE DATABASE IF NOT EXISTS `rcpd`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `rcpd`;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `relays`;
DROP TABLE IF EXISTS `boards`;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `boards` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `board_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `modbus_address` int unsigned NOT NULL,
  `total_relays` int unsigned NOT NULL DEFAULT 16,
  `enabled` enum('Y','N') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Y',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_modbus_address` (`modbus_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `relays` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `board_id` int unsigned NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `relay_num` int unsigned NOT NULL,
  `contact_type` enum('NO','NC') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NO',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_board_relay` (`board_id`, `relay_num`),
  KEY `idx_relays_board_id` (`board_id`),
  CONSTRAINT `fk_relays_board_id` FOREIGN KEY (`board_id`) REFERENCES `boards` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `boards` (`id`, `board_type`, `modbus_address`, `total_relays`, `enabled`) VALUES
  (1, 'R421B16', 1, 16, 'Y'),
  (2, 'R421B16', 2, 16, 'Y'),
  (3, 'R421B16', 3, 16, 'N'),
  (4, 'R421B16', 4, 16, 'N');

INSERT INTO `relays` (`board_id`, `description`, `relay_num`, `contact_type`) VALUES
  (1, 'Server1', 1, 'NO'),
  (1, 'Server2', 2, 'NO'),
  (1, '', 3, 'NO'),
  (1, '', 4, 'NO'),
  (1, '', 5, 'NO'),
  (1, '', 6, 'NO'),
  (1, '', 7, 'NO'),
  (1, '', 8, 'NO'),
  (1, '', 9, 'NO'),
  (1, '', 10, 'NO'),
  (1, '', 11, 'NO'),
  (1, '', 12, 'NO'),
  (1, '', 13, 'NO'),
  (1, '', 14, 'NO'),
  (1, '', 15, 'NO'),
  (1, '', 16, 'NO'),

  (2, 'Server1', 1, 'NO'),
  (2, 'Server2', 2, 'NO'),
  (2, '', 3, 'NO'),
  (2, '', 4, 'NO'),
  (2, '', 5, 'NO'),
  (2, '', 6, 'NO'),
  (2, '', 7, 'NO'),
  (2, '', 8, 'NO'),
  (2, '', 9, 'NO'),
  (2, '', 10, 'NO'),
  (2, '', 11, 'NO'),
  (2, '', 12, 'NO'),
  (2, '', 13, 'NO'),
  (2, '', 14, 'NO'),
  (2, '', 15, 'NO'),
  (2, '', 16, 'NO'),

  (3, 'Server1', 1, 'NO'),
  (3, 'Server2', 2, 'NO'),
  (3, '', 3, 'NO'),
  (3, '', 4, 'NO'),
  (3, '', 5, 'NO'),
  (3, '', 6, 'NO'),
  (3, '', 7, 'NO'),
  (3, '', 8, 'NO'),
  (3, '', 9, 'NO'),
  (3, '', 10, 'NO'),
  (3, '', 11, 'NO'),
  (3, '', 12, 'NO'),
  (3, '', 13, 'NO'),
  (3, '', 14, 'NO'),
  (3, '', 15, 'NO'),
  (3, '', 16, 'NO'),

  (4, 'Server1', 1, 'NO'),
  (4, 'Server2', 2, 'NO'),
  (4, '', 3, 'NO'),
  (4, '', 4, 'NO'),
  (4, '', 5, 'NO'),
  (4, '', 6, 'NO'),
  (4, '', 7, 'NO'),
  (4, '', 8, 'NO'),
  (4, '', 9, 'NO'),
  (4, '', 10, 'NO'),
  (4, '', 11, 'NO'),
  (4, '', 12, 'NO'),
  (4, '', 13, 'NO'),
  (4, '', 14, 'NO'),
  (4, '', 15, 'NO'),
  (4, '', 16, 'NO');
