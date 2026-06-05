-- --------------------------------------------------------
-- Hostitel:                     127.0.0.1
-- Verze serveru:                8.0.17 - MySQL Community Server - GPL
-- OS serveru:                   Win64
-- HeidiSQL Verze:               12.3.0.6649
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Exportování struktury databáze pro
CREATE DATABASE IF NOT EXISTS `rcpd` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `rcpd`;

-- Exportování struktury pro tabulka rcpd.boards
CREATE TABLE IF NOT EXISTS `boards` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `board_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `modbus_address` int(10) unsigned NOT NULL,
  `total_relays` int(10) unsigned NOT NULL,
  `enabled` enum('Y','N') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Y' COMMENT '(DC2Type:enum_enabled_type)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `UNIQ_F3EE4D1325991109` (`modbus_address`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Exportování dat pro tabulku rcpd.boards: ~3 rows (přibližně)
INSERT INTO `boards` (`id`, `board_type`, `modbus_address`, `total_relays`, `enabled`) VALUES
	(1, 'R421B16', 1, 16, 'Y'),
	(2, 'R421B16', 2, 16, 'Y'),
	(3, 'R421B16', 3, 16, 'N'),
	(4, 'R421B16', 4, 16, 'N');

-- Exportování struktury pro tabulka rcpd.messenger_messages
CREATE TABLE IF NOT EXISTS `messenger_messages` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `body` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `headers` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `queue_name` varchar(190) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `available_at` datetime NOT NULL,
  `delivered_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `IDX_75EA56E0FB7336F0` (`queue_name`),
  KEY `IDX_75EA56E0E3BD61CE` (`available_at`),
  KEY `IDX_75EA56E016BA31DB` (`delivered_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Exportování dat pro tabulku rcpd.messenger_messages: ~0 rows (přibližně)

-- Exportování struktury pro tabulka rcpd.relays
CREATE TABLE IF NOT EXISTS `relays` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `board_id` int(10) unsigned DEFAULT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `relay_num` int(10) unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ean` (`board_id`,`relay_num`),
  KEY `IDX_A9EEFEC1E7EC5785` (`board_id`),
  CONSTRAINT `FK_A9EEFEC1E7EC5785` FOREIGN KEY (`board_id`) REFERENCES `boards` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Exportování dat pro tabulku rcpd.relays: ~1 rows (přibližně)
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, 'Server1', 1);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, 'Server2', 2);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 3);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 4);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 5);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 6);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 7);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 8);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 9);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 10);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 11);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 12);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 13);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 14);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 15);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (1, '', 16);

INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, 'Server1', 1);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, 'Server2', 2);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 3);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 4);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 5);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 6);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 7);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 8);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 9);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 10);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 11);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 12);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 13);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 14);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 15);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (2, '', 16);

INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, 'Server1', 1);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, 'Server2', 2);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 3);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 4);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 5);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 6);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 7);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 8);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 9);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 10);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 11);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 12);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 13);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 14);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 15);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (3, '', 16);


INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, 'Server1', 1);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, 'Server2', 2);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 3);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 4);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 5);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 6);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 7);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 8);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 9);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 10);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 11);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 12);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 13);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 14);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 15);
INSERT INTO `relays` (`board_id`, `description`, `relay_num`) VALUES (4, '', 16);

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
