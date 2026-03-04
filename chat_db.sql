-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Hôte : 127.0.0.1
-- Généré le : mer. 04 mars 2026 à 14:46
-- Version du serveur : 10.4.32-MariaDB
-- Version de PHP : 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de données : `chat_db`
--

-- --------------------------------------------------------

--
-- Structure de la table `chat_messages`
--

CREATE TABLE `chat_messages` (
  `id` bigint(20) NOT NULL,
  `sent_at` datetime NOT NULL,
  `sender` varchar(64) NOT NULL,
  `mode` varchar(16) NOT NULL,
  `recipients` text NOT NULL,
  `message_text` text NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Déchargement des données de la table `chat_messages`
--

INSERT INTO `chat_messages` (`id`, `sent_at`, `sender`, `mode`, `recipients`, `message_text`) VALUES
(1, '2026-03-03 14:49:59', 'jj', 'broadcast', '', 'bonjour'),
(2, '2026-03-03 14:53:25', 'vestro', 'private', 'jj', 'ttttt'),
(3, '2026-03-03 16:12:45', 'vestro', 'broadcast', '', 'hello world !'),
(4, '2026-03-03 16:18:49', 'vestro', 'broadcast', '', 'salut'),
(5, '2026-03-03 16:28:20', 'clarice', 'private', 'kasiki', 'hello kasiki'),
(6, '2026-03-03 16:28:59', 'kasiki', 'private', 'clarice', 'who are you'),
(7, '2026-03-04 14:44:56', 'vestro', 'private', 'wasi', 'salut');

--
-- Index pour les tables déchargées
--

--
-- Index pour la table `chat_messages`
--
ALTER TABLE `chat_messages`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT pour les tables déchargées
--

--
-- AUTO_INCREMENT pour la table `chat_messages`
--
ALTER TABLE `chat_messages`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
