# 職位搜尋與申請草稿

Assignment 2 的英文紀錄在 `assignment2/Assignment2_Trying_an_Agent.pdf`。提示和代理回覆按當次執行原文保留。

這份資料依作業「Searching for jobs and preparing applications」的四步來做：按偏好搜尋、去掉已看過或已關閉的職位、按現有經歷評分、只為仍然值得看的職位起草履歷和求職信。

搜尋日是 **2026-10-06**。對象是作業裡的 **CHEUNG Yuk Yuen**，現職物理系 AI Application Trainee。草稿**沒有向任何僱主提交**。

## 建議先看的職位

| 職位 | 分數 | 原因 |
| --- | --- | --- |
| [Ricoh 兼職 Forward Deployed Engineer 實習](https://hk.jobsdb.com/job/94927343) | 79 | 已讀到 JobsDB 全文。香港、歡迎在學學生、工作是實作 AI 方案。須先確認自己仍在學。 |
| [Ricoh AI & Data Associate](https://hk.jobsdb.com/job/94705146) | 81 | 已讀到 JobsDB 全文。歡迎應屆畢業生，有培訓。投遞前仍要核對求職信。 |
| [SmartAge Software Engineer AI](https://www.techjobasia.com/jobs/CTqdRMU_Q1-ODjmWUJia1w---Software-Engineer-AI-(Intern-or-Full-time)) | 54 | 沙田、實習或全職。Android 模擬測試相關，但職缺要求 Flutter 和 IoT，履歷裡沒有。 |
| [Precision Robotics AI Engineer Intern](https://jobs.weekday.works/precision-robotics-(hong-kong)-limited-ai-engineer-intern) | 39 | 機械人軟件測試很接近，但聚合頁要求 C++，而且沒有刊登日期。未補上 C++ 證據前不要投。 |

## 先不要投

- **DBS 2027 Management Associate（AI & Data Science）** 在新加坡，而且要求 Python、Pandas 和 RAG。見 [職缺](https://dbs.wd3.myworkdayjobs.com/DBS_Careers/job/Singapore---Central/XMLNAME-2027-Management-Associate-Programme--Technology-and-AI---Data-Science-_WD88186)。
- **FDM 香港畢業生計劃** 寫明對象是從英國、澳洲或加拿大回港的學生。見 [職缺](https://careers.fdmgroup.com/vacancies/1721/software-engineering-graduate-programme--international-students-hong-kong-based.html)。
- **Ricoh AI Solution Specialist** 已讀到 JobsDB 全文，職稱看起來比見習更高，所以沒有起草。見 [職缺](https://hk.jobsdb.com/job/94904479)。

## 已排除，避免重複申請

- 生產力促進局 Technical Officer, Emerging Applications：頁面寫職位已額滿。
- Macroview Solution Engineer - AI Automation：轉載頁標為已過期。
- PharmCare AI / Application Specialist Trainee：LinkedIn 已停止接受申請，而且該則廣告指向香港大學實習計劃。

## 履歷沒有填寫的欄位

作業沒有寫院校、學位、畢業年份、是否在學、電郵、電話、程式語言和受僱年資。這些在履歷裡保持 `[fill in]`。求職信也不會把 Python、C++ 或 Flutter 寫成已有技能。

## 怎樣使用

```bash
python3 src/server.py
```

瀏覽器打開 `http://127.0.0.1:8765/web/index.html`。

「立即重新搜尋」會向四個公開來源取回職缺：JobsDB（香港）、LinkedIn 公開職缺列表（香港）、JobStreet（新加坡）、Remotive（遠端）。已核對過的舊職位會保留。已關閉的不會重新起草。程式會再讀職缺正文（JobsDB 與 JobStreet 用職位內容、LinkedIn 用公開職缺頁、Remotive 用搜尋結果裡的說明）。讀不到正文的只留在「先不要投」，不會生成求職信。求職信會引用該則廣告的句子，並只接上履歷裡對得上的經歷。

「上傳主履歷」接受 PDF、DOCX、TXT 或 Markdown。原文會抄進草稿，並標出和該職位用詞重疊的句子。檔案留在本機 `data/uploads/` 和 `data/master_cv.json`，不會寫進 `data/profile.json`，也不會自動寄出。

頁面上的「保留審閱」「已提交」「略過」會寫入 `data/tracker.json`。重新載入後狀態跟檔案一樣。已提交或略過的職位會離開起草清單。

每封求職信要先按「預覽求職信」，再按「我已核對，允許下載」，下載連結才會出現。未確認時，伺服器不會送出該職位的履歷或求職信。生成的草稿在本機 `applications/`，不納入版本庫。

```bash
python3 -m unittest tests/test_career_agent.py tests/test_live_search.py
```

申請信在 `applications/<職位id>/`。主履歷在 `applications/master/cv.md`。
