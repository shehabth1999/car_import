# -*- coding: utf-8 -*-
{
    'name': 'Car Import',
    'technical_name': 'car_import',
    'type': 'app',
    'summary': 'Car-import deals for Khaled Automobile / K&T: shipping stages, automatic customer messages, documents',
    'description': """
Car Import (Khaled Automobile GmbH + K&T)
-----------------------------------------
The deal is its own record, not a sales order — `sales`, `account`, `payment`
and `products` are never installed (decision D24).

- CarDeal: one car, one customer, the client's 13 shipping stages, a human-set
  paid / not-paid mark, financing terms, contract amounts and logistics facts.
- ImportStage: the stages and their customer message, editable by ops.
- StageChangeLog: one row per transition, with the outcome of the message.
- Every stage move sends the customer a message automatically on whatever
  channel they use (all stages except cancellation).
""",
    'author': "Genie ERP",
    'website': "https://www.aigeniecrm.com",
    'category': 'Sales',
    'version': '0.1.0',
    'application': True,
    'installable': True,
    'auto_install': False,
    'icon': 'Car',
    'depends': [
        'base', 'notifications', 'contacts', 'crm', 'dashboard', 'chat', 'whatsapp',
        # deliberately NOT 'sales' / 'account' / 'payment' / 'products' — see check_ka_install
    ],
}
