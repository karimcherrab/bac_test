---
id: "THEOREM-SEQ-005"
title: "خاصية المجال الثابت"
type: "theorem"
subject: "رياضيات"
branch: "علوم تجريبية"
chapter: "المتتاليات"
difficulty: "medium"
concepts: ["invariant_interval", "recursive_sequence", "induction"]
methods: ["METHOD-SEQ-013", "METHOD-SEQ-003"]
bac_questions: ["BAC-2008-SCI-EX03-Q1", "BAC-2008-SCI-EX03-Q2"]
---

# خاصية المجال الثابت

## نص المبرهنة
إذا كان u_0 ينتمي إلى I، وإذا كانت f(I)⊂I، فإن كل حدود المتتالية المعرفة بـ u_{n+1}=f(u_n) تنتمي إلى I.

## متى نستعملها؟
تستعمل لإثبات أن حدود متتالية تراجعية تبقى محصورة داخل مجال.

## فكرة البرهان
نستعمل الاستدلال بالتراجع: u_0∈I. إذا كان u_n∈I، فبما أن f(I)⊂I فإن u_{n+1}=f(u_n)∈I.

## الأخطاء الشائعة
- عدم إثبات f(I)⊂I.
- نسيان التحقق من u_0∈I.
- استعمال المجال الثابت دون تراجع.
