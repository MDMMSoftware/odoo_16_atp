{
    'name': 'Fleet Extension',
    'version' : '1.0',
    'summary':'Fleet Vehicle',
    'author': 'Mudon Maung Maung Co.,Ltd',
    'website': 'www.mudonmaungmaung.com',
    'depends':['fleet','account','account_cashbook','sale','purchase','stock_extension'],
    'category': "Tools",
    "installable": True,
    'data':[
        'security/security.xml', 
        'security/ir.model.access.csv',  
        'views/fleet_vehicle_views.xml',
        'views/inherited_views.xml',   
        'views/configurations.xml',  
        'views/fleet_attachment.xml'           
    ],
    'license': 'LGPL-3',
}