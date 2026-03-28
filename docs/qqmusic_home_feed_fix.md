# QQ音乐主页推荐数据修复

## 问题描述

QQ音乐 `get_home_feed()` API 返回的数据为空。

## 根本原因

API响应的实际数据结构与代码中的解析逻辑不匹配。

### 实际API响应结构

```json
{
  "v_shelf": [
    {
      "id": 207,
      "v_niche": [
        {
          "v_card": [
            {
              "type": 200,  // type=200 表示歌曲卡片
              "id": 202220046,
              "title": "雨天",
              "subtitle": "汪苏泷",  // 歌手名
              "cover": "https://...",
              "subid": "013eCGpv2RE8Ax",  // 歌曲MID
              "time": 6684554615616
            }
          ]
        }
      ]
    }
  ]
}
```

### 原有代码的问题

原有代码尝试从以下位置提取数据：
- `result['v_shelf'][0]['item_list']` （不存在）
- `result['songlist']`、`result['songs']` 等（也不存在）

但实际歌曲数据位于：
- `result['v_shelf'][].v_niche[].v_card[]` 中，且需要过滤 `type=200` 的卡片

## 修复方案

更新 `services/cloud/qqmusic/qqmusic_service.py` 中的 `get_home_feed()` 方法：

1. 遍历 `v_shelf` 数组
2. 遍历每个 shelf 的 `v_niche` 数组
3. 遍历每个 niche 的 `v_card` 数组
4. 过滤 `type=200` 的卡片（歌曲卡片）
5. 提取以下字段：
   - `id` / `songid`: 歌曲ID
   - `title`: 歌曲标题
   - `subtitle` / `singer`: 歌手名
   - `cover`: 封面URL
   - `subid` / `mid`: 歌曲MID
   - `time`: 时长

## 测试结果

修复后成功提取到36首歌曲：

```
✓ Found 36 songs

Sample songs:
1. 晴 - 汪苏泷 (ID: 5665622, MID: k0022vbocvs)
2. Take Yourself Home (Acoustic) - Troye Sivan (ID: 274878784, MID: j00338xao9v)
3. 微光海洋 - 周深/王者荣耀 (ID: 273809180, MID: y0034ar6em1)
4. 无人知晓 - 田馥甄 (ID: 278479738, MID: x0034kpe1ez)
5. Something - 娜琏 (ID: 492482192, MID: )
```

## 相关文件

- `services/cloud/qqmusic/client.py:666-673` - API客户端方法
- `services/cloud/qqmusic/qqmusic_service.py:862-916` - 服务层解析方法
- `ui/views/online_music_view.py:202` - UI调用处
