# 测试数据的生成
基于 Fake 造测试数据，电商场景包含用户、商品、订单、支付、物流等多个关联环节，非常适合测试多表查询、事务和数据一致性。以下是6张核心关联表的设计:

| 表名 | 核心作用 | 关键字段（含外键） | 关联关系 |
| :--- | :--- | :--- | :--- |
| **user（用户表）** | 存储用户基础信息 | user_id（主键）、username、phone、address | 1个用户可对应多个订单（1:N） |
| **product（商品表）** | 存储商品信息 | product_id（主键）、name、price、stock、category_id | 1个分类对应多个商品（1:N） |
| **product_category（商品分类表）** | 对商品进行分类 | category_id（主键）、name、parent_id | 支持分类嵌套（如“电子产品-手机”） |
| **order（订单表）** | 存储订单主信息 | order_id（主键）、user_id（外键）、total_amount、order_status、create_time | 1个用户对应多个订单（N:1）；1个订单对应多个订单项（1:N） |
| **order_item（订单项表）** | 存储订单中的商品明细 | item_id（主键）、order_id（外键）、product_id（外键）、quantity、item_price | 关联订单和商品（N:1 对应订单，N:1 对应商品） |
| **payment（支付表）** | 存储订单支付信息 | payment_id（主键）、order_id（外键）、pay_amount、pay_method、pay_time | 1个订单对应1笔支付（1:1） |


表间关联逻辑（级级关联核心）
通过“外键+业务规则”实现多层级关联，模拟真实数据流向，具体逻辑如下：
1. **基础层**：先有`product_category`（分类），才能创建`product`（商品），商品必须归属一个分类。
2. **用户层**：`user`（用户）是独立基础数据，后续订单需绑定用户。
3. **订单层**：创建`order`（订单）时，必须关联已存在的`user_id`；创建`order_item`（订单项）时，必须关联已存在的`order_id`和`product_id`。
4. **支付层**：创建`payment`（支付）时，必须关联已存在的`order_id`，且支付金额需与订单总金额一致（业务逻辑约束）。