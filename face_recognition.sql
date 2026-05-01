/*
 Navicat Premium Dump SQL

 Source Server         : localhost
 Source Server Type    : MySQL
 Source Server Version : 80036 (8.0.36)
 Source Host           : localhost:3306
 Source Schema         : face_recognition

 Target Server Type    : MySQL
 Target Server Version : 80036 (8.0.36)
 File Encoding         : 65001

 Date: 19/03/2026 21:44:14
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for analysis
-- ----------------------------
DROP TABLE IF EXISTS `analysis`;
CREATE TABLE `analysis`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` int NULL DEFAULT NULL COMMENT '用户ID',
  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '用户名',
  `image_path` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '图片路径',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `payload_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '分析数据',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '分析记录表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of analysis
-- ----------------------------
INSERT INTO `analysis` VALUES (1, NULL, '1', 'static/uploads/4714812e8ce44c639f4f33bfc64c1dad.jpg', '2026-03-19 13:39:08', '{\"raw\": {\"error_code\": 0, \"error_msg\": \"SUCCESS\", \"log_id\": 3057032935, \"timestamp\": 1773927547, \"cached\": 0, \"result\": {\"face_num\": 1, \"face_list\": [{\"face_token\": \"5f0b8a77d3fe073a34a9d80955404fb9\", \"location\": {\"left\": 88.71, \"top\": 519.26, \"width\": 938, \"height\": 1024, \"rotation\": 2}, \"face_probability\": 1, \"angle\": {\"yaw\": 8.62, \"pitch\": 18.65, \"roll\": -3.27}, \"landmark\": [{\"x\": 307.76, \"y\": 650.43}, {\"x\": 747.55, \"y\": 667.28}, {\"x\": 503.64, \"y\": 892.65}, {\"x\": 516.37, \"y\": 1195.22}], \"landmark72\": [{\"x\": 85.63, \"y\": 594.9}, {\"x\": 89.8, \"y\": 761.97}, {\"x\": 116.56, \"y\": 931.2}, {\"x\": 163.81, \"y\": 1098.66}, {\"x\": 236.35, \"y\": 1275.2}, {\"x\": 353.82, \"y\": 1462.26}, {\"x\": 515.99, \"y\": 1559.61}, {\"x\": 687.15, \"y\": 1491.07}, {\"x\": 836.97, \"y\": 1317.13}, {\"x\": 919.57, \"y\": 1135.11}, {\"x\": 968.79, \"y\": 965.65}, {\"x\": 1004.99, \"y\": 797.08}, {\"x\": 1023.74, \"y\": 629.03}, {\"x\": 199.56, \"y\": 650.02}, {\"x\": 252.71, \"y\": 632.56}, {\"x\": 307.43, \"y\": 630.69}, {\"x\": 360.6, \"y\": 638.92}, {\"x\": 409.03, \"y\": 663.79}, {\"x\": 356.6, \"y\": 669.51}, {\"x\": 298.98, \"y\": 674.67}, {\"x\": 245.09, \"y\": 666.99}, {\"x\": 307.76, \"y\": 650.43}, {\"x\": 147.23, \"y\": 561.35}, {\"x\": 220.24, \"y\": 523.65}, {\"x\": 294.52, \"y\": 538.56}, {\"x\": 365.95, \"y\": 563.31}, {\"x\": 429.08, \"y\": 611.62}, {\"x\": 354.87, \"y\": 600.51}, {\"x\": 284.02, \"y\": 581.85}, {\"x\": 212.86, \"y\": 567.54}, {\"x\": 644.31, \"y\": 672.48}, {\"x\": 695.74, \"y\": 652.41}, {\"x\": 748.56, \"y\": 648.88}, {\"x\": 804.54, \"y\": 655.38}, {\"x\": 859.9, \"y\": 673.74}, {\"x\": 808.79, \"y\": 686.91}, {\"x\": 751.64, \"y\": 692.48}, {\"x\": 695.77, \"y\": 681.64}, {\"x\": 747.55, \"y\": 667.28}, {\"x\": 621.42, \"y\": 618.77}, {\"x\": 692.48, \"y\": 574.08}, {\"x\": 772.24, \"y\": 558.29}, {\"x\": 851.84, \"y\": 551.95}, {\"x\": 929.43, \"y\": 597.42}, {\"x\": 854.97, \"y\": 592.75}, {\"x\": 777.28, \"y\": 601.61}, {\"x\": 699.71, \"y\": 612.93}, {\"x\": 455.19, \"y\": 677.18}, {\"x\": 436.64, \"y\": 753.24}, {\"x\": 418.05, \"y\": 830.3}, {\"x\": 384.31, \"y\": 921.86}, {\"x\": 437.26, \"y\": 934.2}, {\"x\": 577.36, \"y\": 936.7}, {\"x\": 642.16, \"y\": 924.15}, {\"x\": 607.41, \"y\": 831.36}, {\"x\": 595.64, \"y\": 755.59}, {\"x\": 583.46, \"y\": 679.71}, {\"x\": 503.64, \"y\": 892.65}, {\"x\": 341.73, \"y\": 1156.71}, {\"x\": 387.09, \"y\": 1050.37}, {\"x\": 506.46, \"y\": 1033.39}, {\"x\": 640.06, \"y\": 1056.11}, {\"x\": 709.91, \"y\": 1165.94}, {\"x\": 659.85, \"y\": 1340.89}, {\"x\": 514.48, \"y\": 1417.97}, {\"x\": 378.35, \"y\": 1334.65}, {\"x\": 396.03, \"y\": 1086.07}, {\"x\": 506.41, \"y\": 1073.67}, {\"x\": 630.92, \"y\": 1090.32}, {\"x\": 633.63, \"y\": 1294.15}, {\"x\": 516.41, \"y\": 1345.68}, {\"x\": 407.78, \"y\": 1287.16}], \"gender\": {\"type\": \"female\", \"probability\": 0.98}, \"glasses\": {\"type\": \"none\", \"probability\": 0.98}, \"eye_status\": {\"left_eye\": 0.9817097783, \"right_eye\": 0.9335839152}, \"face_shape\": {\"type\": \"oval\", \"probability\": 0.51}, \"emotion\": {\"type\": \"angry\", \"probability\": 0.9798828959}, \"face_type\": {\"type\": \"human\", \"probability\": 0.88}, \"mask\": {\"type\": 0, \"probability\": 1}}]}}, \"faces\": [{\"emotion_type\": \"angry\", \"emotion_cn\": \"愤怒\", \"secondary_emotion_cn\": \"生气\", \"emotion_prob\": 0.9798828959, \"emotion_interval\": {\"center\": 0.9798828959, \"low\": 0.9298828959, \"high\": 1.0}, \"location\": {\"left\": 88.71, \"top\": 519.26, \"width\": 938.0, \"height\": 1024.0, \"rotation\": 2.0}, \"face_center\": {\"x\": 557.71, \"y\": 1031.26}, \"psych\": {\"status\": \"focus\", \"status_cn\": \"需要重点关注\", \"reason\": \"负面情绪显著\"}}], \"stats\": {\"total_faces\": 1, \"emotion_counts\": {\"愤怒\": 1}, \"secondary_emotion_counts\": {\"生气\": 1}, \"status_counts\": {\"状态良好\": 0, \"需要关注\": 0, \"需要重点关注\": 1}, \"focus_students\": [{\"face_center\": {\"x\": 557.71, \"y\": 1031.26}, \"emotion\": \"生气\", \"emotion_prob\": 0.9798828959, \"reason\": \"负面情绪显著\"}]}, \"seat_layout_meta\": {\"path\": \"seat_layout.json\", \"image_size\": {\"width\": 1280, \"height\": 720}}, \"image_url\": \"static/uploads/4714812e8ce44c639f4f33bfc64c1dad.jpg\"}');

-- ----------------------------
-- Table structure for user
-- ----------------------------
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键',
  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '用户名',
  `password` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '密码',
  `name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '昵称',
  `role` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '角色',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '用户表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of user
-- ----------------------------
INSERT INTO `user` VALUES (1, '1', '1', '张三', NULL);

SET FOREIGN_KEY_CHECKS = 1;
