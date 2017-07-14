odoo.define('pos_sub_product.pos', function (require) {
"use strict";
    // Add multiple screen for Sub Products.
	var gui = require('point_of_sale.gui');
	var models = require('point_of_sale.models');
	var screens = require('point_of_sale.screens');
	var core = require('web.core');
	var utils = require('web.utils');
	var PopupWidget = require('point_of_sale.popups');
	var DB = require('point_of_sale.DB');
	var formats = require('web.formats');
	var Model = require('web.DataModel');
	var PosBaseWidget = require('point_of_sale.BaseWidget');
	var _initialize_orderline_ = models.Orderline.prototype;
	var round_di = utils.round_decimals;

	var QWeb = core.qweb;
	var _t = core._t;

/* ********************************************************
Overload: point_of_sale.Models

********************************************************** */
	
	var _super_posmodel = models.PosModel.prototype;
	
    //  Add "Sub Product Type" field in existing POS Category Model.
	models.PosModel = models.PosModel.extend({
	    initialize: function (session, attributes) {
	        var partner_model = _.find(this.models, function(model){
	            return model.model === 'pos.category';
	        });
	        partner_model.domain = [['is_sub_product_type','=',false]]
	        return _super_posmodel.initialize.call(this, session, attributes);
	    },
	});

    //  Add below fields in Sub Product Line Model.
	models.PosModel.prototype.models.push({
        model:  'sub.product.line',
        fields: ['category_id',
                 'product_tmpl_id',
                 'product_ids',
                 ],
        loaded: function(self,line){
        	self.db.add_line(line);
        },
    });

    // Add Following list of fields in to Products
	models.load_fields("product.product", ['sub_product_line', 'sub_product_count','is_parent_product','is_sub_product']);
	


/* ********************************************************
Overload: point_of_sale.Screens

********************************************************** */

	screens.ProductListWidget.include({
		
        init: function(parent, options) {
            this._super(parent,options);
            var self = this;
            // OVERWRITE 'click_product_handler' function to do
            // a different behaviour if template with one or many variants
            // are selected.
            this.click_product_handler = function(event){
            	var product = self.pos.db.get_product_by_id(this.dataset.productId);
                if (product.sub_product_count == 0) {
                    options.click_product_action(product);
                }
                else{
                	self.gui.show_screen('select_sub_product_screen',{product_id:product});
                }
            };
        },
        
        // Render all Products as per below conditions
	    render_product: function(product){
	        self = this;
	        if (product.sub_product_count == 0){
	            // Normal Display(Odoo Deafault)
	            return this._super(product);
	        }
	        else{
                // Custom View(as per requirement)
	            var cached = this.product_cache.get_node(product.id);
	            if(!cached){
	                var image_url = this.get_product_image_url(product);
	                var product_html = QWeb.render('Product',{ 
	                        widget:  this, 
	                        product: product, 
	                        image_url: this.get_product_image_url(product),
	                    });
	                var product_node = document.createElement('div');
	                product_node.innerHTML = product_html;
	                product_node = product_node.childNodes[1];
	                this.product_cache.cache_node(product.id,product_node);
	                return product_node;
	            }
	            return cached;
	        }
	    },
        
        // Render all Elements of Products as above selected Products
	    renderElement: function() {
	        var el_str  = QWeb.render(this.template, {widget: this});
	        var el_node = document.createElement('div');
	            el_node.innerHTML = el_str;
	            el_node = el_node.childNodes[1];

	        if(this.el && this.el.parentNode){
	            this.el.parentNode.replaceChild(el_node,this.el);
	        }
	        this.el = el_node;

	        var list_container = el_node.querySelector('.product-list');
	        for(var i = 0, len = this.product_list.length; i < len; i++){
	        	if (!this.product_list[i].is_sub_product){
		            var product_node = this.render_product(this.product_list[i]);
		            product_node.addEventListener('click',this.click_product_handler);
		            list_container.appendChild(product_node);
	        	}
	        }
	    },
	});

// Create new screem to select Sub Product
var SelectSubProductScreen = screens.ScreenWidget.extend({
    template:'SelectSubProductScreen',

    init: function(parent, options){
        this._super(parent, options);
    },
    
    start: function(){
    	this._super();
        var self = this;
        // Define Sub Product Widget
        this.sub_product_list_widget = new AttributeListWidget(this,{});
        this.sub_product_list_widget.replace(this.$('.placeholder-AttributeListWidget'));

        // Add behaviour on Cancel Button
        this.$('#variant-popup-cancel').off('click').click(function(){
        	self.gui.back();
        });
        this.$('#create_order').off('click').click(function(){
        	self.next();
        });
    },
    
    // Render number of screens as per selected sub product categories.
    next: function(){
    	var main_product_id = this.sub_product_list_widget.product_product_id
    	var number_of_line = this.sub_product_list_widget.number_of_line
    	if (main_product_id.sub_product_line && main_product_id.sub_product_line[number_of_line]){
    		this.sub_product_list_widget.filters = {}
    		this.sub_product_list_widget.set_attribute_list(main_product_id.sub_product_line[number_of_line], main_product_id.product_tmpl_id, main_product_id, number_of_line + 1);
    	}
    	else{
    		self.pos.get_order().add_product(this.pos.db.get_product_by_id(this.sub_product_list_widget.product_product_id.id), {sub_product_ids: [8,9,10] })
        	for (var key in this.sub_product_list_widget.dict_for_selection) {
        		for(var i=0 ; i < this.sub_product_list_widget.dict_for_selection[key].length; i++){
        			self.pos.get_order().add_product(this.pos.db.get_product_by_id(this.sub_product_list_widget.dict_for_selection[key][i]))
        		}
        	}
        	self.gui.show_screen('products');
    	}
    },

    // Display number of screens as per selected sub product categories.
    show: function(options){
    	this._super();
        var self = this;
        var product_id = self.gui.get_current_screen_param('product_id');
        // Display Name of Template
        this.$('#variant-title-name').html(product_id.name);
        var sub_product_list = []

        // Render Sub Product
        //var sub_product_list  = product_id.sub_product_line;
        for (var i = 0, len = product_id.sub_product_line.length; i < len; i++) {
        	sub_product_list.push(this.pos.db.get_sub_product_line_by_id(product_id.sub_product_line[i]).product_ids)
        }
        this.sub_product_list_widget.filters = {}
        var number = 1
        this.sub_product_list_widget.dict_for_selection = {}
        this.sub_product_list_widget.set_attribute_list(product_id.sub_product_line[0], product_id.product_tmpl_id, product_id, number);

        this._super();
    },
});

gui.define_screen({name:'select_sub_product_screen', widget: SelectSubProductScreen});


/* ********************************************************
Overload: point_of_sale.PosDB

- Add to local storage Product Templates Data.
- Link Sub Product to Product Templates.
- Add an extra field 'is_sub_product' on product object. the product
    will be display on product list, only if it is the sub product;
    Otherwise, the product will be displayed only on Template Screen.
- Add an extra field 'sub_product_count' on product object that
    indicates the number of variant of the template of the product.
*********************************************************** */
    DB.include({
        init: function(options){
            this.sub_product_line_by_id = {};
            this._super(options);
        },

        get_sub_product_line_by_id: function(line){
            return this.sub_product_line_by_id[line];
        },

        add_line: function(line){
        	for(var i=0 ; i < line.length; i++){
                // store Product Attribute Values
                this.sub_product_line_by_id[line[i].id] = line[i];
            }
        },
    });
});
