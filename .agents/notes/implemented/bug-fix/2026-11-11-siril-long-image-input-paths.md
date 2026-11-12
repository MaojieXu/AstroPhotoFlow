# Agent Note: Siril Windows 长图像路径的调用内暂存

Status: Implemented

## Problem

节点 UI 的真实 RGB 回归使用长文件名后，Siril 的 load 将运行目录中的绝对输入路径截断并报文件不存在。改用相对参数仍受到底层文件读取的 Windows 路径限制。原图能够由平台正常读取，问题发生在 Siril 读取阶段。

## Decision

在独立 Bundle 的图像读取层，仅当 Windows 主图像输入路径达到限制时，将完整文件复制到本次成员工作目录的短文件名。保留普通路径流程、压缩 FITS 的双后缀、原输入及其来源记录，输出仍按既有计划检查与登记。

## Alternatives considered

缩短测试文件名会掩盖实际文件选择流程的故障。相对路径不足以绕过底层读取限制。修改素材名或原件位置会破坏稳定身份和原件保护。所有输入都复制会增加普通调用的 IO。

## Consequences

新增 Windows 长路径和压缩 FITS 后缀回归，临时文件归调用目录所有。长路径调用增加一次暂存复制，普通调用不增加复制。平台和原件身份保持一致，Siril 使用可读取的短路径副本。
