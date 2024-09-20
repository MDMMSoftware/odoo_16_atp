from odoo.exceptions import ValidationError, UserError
from xlrd import open_workbook
import base64

def get_excel_datas(sheets):
    result = []
    for s in sheets:
        headers = []
        header_row = 0
        for hcol in range(0, s.ncols):
            headers.append(s.cell(header_row, hcol).value)
                        
        result.append(headers)
        
        for row in range(header_row + 1, s.nrows):
            values = []
            for col in range(0, s.ncols):
                values.append(s.cell(row, col).value)
            result.append(values)
    return result

def get_headers(line,header_fields,header_indexes):
    if line[0].strip().lower() not in header_fields:
        raise ValidationError("Error while processing the header line %s.\n\nPlease check your Excel separator as well as the column header fields") % line
    else:
        for header in header_fields:
            header_indexes[header] = -1  
                    
        col_count = 0
        for ind in range(len(line)):
            if line[ind] == '':
                col_count = ind
                break
            elif ind == len(line) - 1:
                col_count = ind + 1
                break
        
        for i in range(col_count):                
            header = line[i].strip().lower()
            if header not in header_fields:
                raise ValidationError('Invalid Excel File, Header Field %s is not supported !'% header)
            else:
                header_indexes[header] = i
                            
        for header in header_fields:
            if header_indexes[header] < 0:  
                raise ValidationError('Invalid Excel File, Header Field %s is missing !'% header) 

def read_and_validate_datas(self,header_fields,header_indexes):   
    if self.data:   
        if '.xls' not in self.import_fname and '.xlsx'  not in self.import_fname:
            raise UserError("Invalid Excel file format") 
        import_file = self.data                

        header_line = True
        lines = base64.decodestring(import_file)
        wb = open_workbook(file_contents=lines)
        excel_rows = get_excel_datas(wb.sheets())
        all_data = []      
        
        for line in excel_rows:
            if not line or line and line[0] and line[0] in ['', '#']:
                continue            
            if header_line:
                get_headers(line, header_fields, header_indexes)
                header_line = False                           
            elif line and line[0] and line[0] not in ['#', '']:
                import_vals = {}                
                for header in header_fields:    
                    import_vals[header] = line[header_indexes[header]]              
                all_data.append(import_vals)
        return all_data
    else:
        raise ValidationError('Please First Upload Your File.')  