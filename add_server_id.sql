USE autotrader;

-- 添加 server_id 字段到 user_sessions 表
ALTER TABLE user_sessions 
ADD COLUMN server_id VARCHAR(10) AFTER token; 