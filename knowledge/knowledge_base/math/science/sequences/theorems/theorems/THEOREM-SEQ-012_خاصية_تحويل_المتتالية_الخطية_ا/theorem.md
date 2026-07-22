---
id: "THEOREM-SEQ-012"
title: "خاصية تحويل المتتالية الخطية التراجعية إلى هندسية"
type: "theorem"
subject: "رياضيات"
branch: "علوم تجريبية"
chapter: "المتتاليات"
difficulty: "medium"
concepts: ["linear_recursive_sequence", "geometric_transformation", "fixed_point"]
methods: ["METHOD-SEQ-004"]
bac_questions: ["BAC-2008-SCI-EX02-Q3", "BAC-2010-SCI-EX01-Q3", "BAC-2014-SCI-EX01A-Q1"]
---

# خاصية تحويل المتتالية الخطية التراجعية إلى هندسية

## نص المبرهنة
إذا كانت u_{n+1}=a u_n+b وكانت L تحقق L=aL+b، فإن v_n=u_n-L تحقق v_{n+1}=a v_n.

## متى نستعملها؟
تستعمل لاستخراج الحد العام والنهاية للمتتاليات التراجعية الخطية.

## فكرة البرهان
v_{n+1}=u_{n+1}-L=a u_n+b-L=a u_n-(aL)=a(u_n-L)=a v_n.

## الأخطاء الشائعة
- عدم حساب L أولًا.
- خطأ في إشارة v_n=u_n-L.
- نسيان الرجوع إلى u_n.
