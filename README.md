# 職位搜尋與申請草稿

這份資料依作業「Searching for jobs and preparing applications」的四步來做：按偏好搜尋、去掉已看過或已關閉的職位、按現有經歷評分、只為仍然值得看的職位起草履歷和求職信。

搜尋日是 **2026-10-06**。對象是作業裡的 **CHEUNG Yuk Yuen（張煜源）**，現職物理系 AI Application Trainee。草稿**沒有向任何僱主提交**。

## 建議先看的職位

| 職位 | 分數 | 原因 |
| --- | --- | --- |
| [Ricoh 兼職 Forward Deployed Engineer 實習](https://hk.jobsdb.com/job/94927343) | 69 | 香港、歡迎在學學生、工作是實作 AI 方案。須先確認自己仍在學。 |
| [Ricoh AI & Data Associate](https://hk.jobsdb.com/job/94705146) | 71 | 歡迎應屆畢業生，有培訓。完整職缺當日未能打開，投遞前要再讀全文。 |
| [SmartAge Software Engineer AI](https://www.techjobasia.com/jobs/CTqdRMU_Q1-ODjmWUJia1w---Software-Engineer-AI-(Intern-or-Full-time)) | 54 | 沙田、實習或全職。Android 模擬測試相關，但職缺要求 Flutter 和 IoT，履歷裡沒有。 |
| [Precision Robotics AI Engineer Intern](https://jobs.weekday.works/precision-robotics-(hong-kong)-limited-ai-engineer-intern) | 39 | 機械人軟件測試很接近，但聚合頁要求 C++，而且沒有刊登日期。未補上 C++ 證據前不要投。 |

## 先不要投

- **DBS 2027 Management Associate（AI & Data Science）** 在新加坡，而且要求 Python、Pandas 和 RAG。見 [職缺](https://dbs.wd3.myworkdayjobs.com/DBS_Careers/job/Singapore---Central/XMLNAME-2027-Management-Associate-Programme--Technology-and-AI---Data-Science-_WD88186)。
- **FDM 香港畢業生計劃** 寫明對象是從英國、澳洲或加拿大回港的學生。見 [職缺](https://careers.fdmgroup.com/vacancies/1721/software-engineering-graduate-programme--international-students-hong-kong-based.html)。
- **Ricoh AI Solution Specialist** 只取得職位卡摘要，職稱看起來比見習更高。見 [職缺](https://hk.jobsdb.com/job/94904479)。

## 已排除，避免重複申請

- 生產力促進局 Technical Officer, Emerging Applications：頁面寫職位已額滿。
- Macroview Solution Engineer - AI Automation：轉載頁標為已過期。
- PharmCare AI / Application Specialist Trainee：LinkedIn 已停止接受申請，而且該則廣告指向香港大學實習計劃。

## 履歷沒有填寫的欄位

作業沒有寫院校、學位、畢業年份、是否在學、電郵、電話、程式語言和受僱年資。這些在履歷裡保持 `[fill in]`。求職信也不會把 Python、C++ 或 Flutter 寫成已有技能。

## 怎樣使用

```bash
python3 src/career_agent.py
python3 -m unittest tests/test_career_agent.py
```

然後打開 `web/index.html`。頁面上可以把職位標成保留、已提交或略過，狀態存在瀏覽器本機。檔案 `data/tracker.json` 是給腳本用的狀態；把某一則的 `applied` 改成 `true` 後再執行腳本，該職位會從起草清單消失。

申請信在 `applications/<職位id>/`。主履歷在 `applications/master/cv.md`。
