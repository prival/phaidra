define(['jquery', 'underscore', 'backbone', 'utils', 'text!/templates/js/reader/notes/about-sentence.html', 'daphne', 'morea'], function($, _, Backbone, Utils, Template, Daphne, Morea) { 

	var View = Backbone.View.extend({
		tagName: 'div', 
		template: _.template(Template),
		events: { 
			'click .parse-tree-view': 'showParseTree',
			'click .alignment-view': 'showAlignment'
		},
		initialize: function(options) {
			this.options = options;
		},
		render: function() {
			this.$el.html(this.template({ 
				word: this.model.attributes,
				langs: this.options.langs,
				readableLang: Utils.getReadableLang,
				lang: this.options.lang || LOCALE
			}));
			this.$el.find('a').tooltip();
			return this;	
		},
		showParseTree: function(e) {
			e.preventDefault();

			var selectedWord = this.collection.words.findWhere({ selected: true });
			var sentence = this.collection.words.where({ sentenceCTS: selectedWord.get('sentenceCTS') });
			var words = sentence.map(function(el, i) {
				el.attributes.id = el.attributes.tbwid;
				return el.attributes;
			});

			new Daphne('[data-toggle="daphne"]', {
				data: words,
				mode: 'edit',
				height: 600,
				width: 1000,
				initialScale: 0.9
			});

			$('#parse-tree-modal').modal('show');
		},
		showAlignment: function(e) {
			e.preventDefault();

			// HACK til I fix the plugin
			$('[data-toggle="morea"]').html('');

			new Morea('[data-toggle="morea"]', {
				dataUrl: this.model.get('sentence_resource_uri'),
				mode: 'view'
			});

			$('#alignment-modal').modal('show');
		}
	});

	return View;

});
